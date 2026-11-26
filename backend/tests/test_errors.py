"""Error mapping (section 6.9), including the one case that is NOT an error.

The distinction that matters: QuotaExhausted and ProviderOverloaded abort the analysis, while
any other LLMError is absorbed by the pipeline (those flags become "rejected", are scored as UN,
and the client gets a 200 with complete=false).
"""
from __future__ import annotations

import asyncio

import pytest

from privascore.llm import LLMError, ProviderOverloaded, QuotaExhausted


def _raise(exc):
    def f(system, user):
        raise exc
    return f


@pytest.fixture
def break_llm(client):
    pipeline = client.app.state.pipeline
    real = pipeline.client.complete_json

    def install(exc):
        pipeline.client.complete_json = _raise(exc)
    yield install
    pipeline.client.complete_json = real


def _post(client, policy_text):
    return client.post("/api/v1/evaluate", json={"text": policy_text})


def test_quota_exhausted_is_429(client, policy_text, break_llm):
    break_llm(QuotaExhausted("gemini: daily quota reached"))
    r = _post(client, policy_text)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "LLM_QUOTA"
    assert "retry-after" not in r.headers        # a daily cap is hours away, so we promise no time
    assert "quota reached" not in r.text          # provider text never reaches the client


def test_provider_overloaded_is_503_not_429(client, policy_text, break_llm):
    """ProviderOverloaded subclasses QuotaExhausted, so the order of the except clauses matters."""
    break_llm(ProviderOverloaded("gemini: still overloaded"))
    r = _post(client, policy_text)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "LLM_OVERLOADED"
    assert r.headers["retry-after"] == "120"


def test_a_plain_llm_error_gives_partial_results_not_an_error(client, policy_text, break_llm):
    break_llm(LLMError("gemini: gave up after 2 attempts"))
    r = _post(client, policy_text)
    assert r.status_code == 200
    d = r.json()
    assert d["scores"]["complete"] is False
    assert d["scores"]["rejected_flags"], "flags that got no answer must be listed"
    rejected = [f for f in d["flags"] if f["status"] == "rejected"]
    assert rejected and all(f["state"] == "UN" for f in rejected)   # scored as Unclear
    assert all(f["rationale"] is None and f["evidence"] == [] for f in rejected)
    assert "gave up after" not in r.text


def test_busy_when_the_gate_is_held(client, policy_text):
    """A second analysis while one runs gets BUSY at once, instead of queueing silently.
    A semaphore with zero permits is exactly what a running analysis leaves behind."""
    app = client.app
    real_gate = app.state.gate
    app.state.gate = asyncio.Semaphore(0)
    try:
        r = _post(client, policy_text)
    finally:
        app.state.gate = real_gate
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "BUSY"
    assert r.headers["retry-after"] == "30"


def test_unknown_field_is_rejected(client, policy_text):
    r = client.post("/api/v1/evaluate", json={"text": policy_text, "scopes": "consumer"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


def test_bad_scope_is_rejected(client, policy_text):
    r = client.post("/api/v1/evaluate", json={"text": policy_text, "scope": "enterprise"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


def test_company_name_length_is_capped(client, policy_text):
    r = client.post("/api/v1/evaluate", json={"text": policy_text, "company_name": "x" * 121})
    assert r.status_code == 422


def test_an_unexpected_exception_is_a_generic_500(client_no_reraise, policy_text):
    """In production an unexpected exception becomes a generic 500 with no internal detail.
    (TestClient re-raises server exceptions by default, so this one needs a plain client.)"""
    c = client_no_reraise
    c.app.state.pipeline.client.complete_json = _raise(ZeroDivisionError("secret internal detail"))
    r = _post(c, policy_text)
    assert r.status_code == 500
    assert r.json()["error"] == {"code": "INTERNAL",
                                 "message": "Something went wrong on our side.",
                                 "retry_after_s": None}
    assert "secret internal detail" not in r.text


def test_every_error_body_has_the_same_shape(client):
    r = client.post("/api/v1/evaluate", json={"text": "tiny"})
    assert set(r.json()["error"]) >= {"code", "message", "retry_after_s"}


# --- the fallback model (settings.llm_fallback_model)
#
# The provider's daily cap is per model, so when the primary model is spent a different one may
# still answer. Accuracy differs between models, so the one that actually answered must be named
# in the response; a silent swap would misreport how the result was produced.

def _fallback_client(client_factory, **overrides):
    return client_factory(llm_provider="mock", bert="off", bert_required=False,
                          rate_limit_per_client=0, **overrides)


def test_fallback_answers_when_the_primary_model_is_out_of_quota(client_factory, policy_text):
    with _fallback_client(client_factory, llm_fallback_model="fallback-model") as c:
        pipeline = c.app.state.pipeline
        pipeline.client.complete_json = _raise(QuotaExhausted("mock: daily quota reached"))
        r = c.post("/api/v1/evaluate", json={"text": policy_text})
    assert r.status_code == 200
    # The fallback's own client answered, so the response must name IT, not the primary model.
    assert r.json()["meta"]["model"] == "fallback-model"


def test_no_fallback_configured_still_fails_with_the_quota_error(client_factory, policy_text):
    """The fallback is opt-in: without one the behaviour is exactly as before."""
    with _fallback_client(client_factory) as c:
        c.app.state.pipeline.client.complete_json = _raise(QuotaExhausted("mock: daily quota reached"))
        r = c.post("/api/v1/evaluate", json={"text": policy_text})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "LLM_QUOTA"


def test_both_models_failing_reports_every_call_that_was_billed(client_factory, policy_text):
    """The route refunds the budget only when NOTHING was billed. If the primary model billed a
    call before running out, a refund would hand back budget that was really spent, so the count
    on the escaping error has to cover both attempts."""
    with _fallback_client(client_factory, llm_fallback_model="fallback-model") as c:
        pipeline = c.app.state.pipeline
        real_extract = pipeline._extract

        def extract(text, scope, company_name, client=None):
            exc = QuotaExhausted("mock: daily quota reached")
            exc.completed_llm_calls = 1          # each attempt billed one call before failing
            raise exc

        pipeline._extract = extract
        seen = {}
        from app.routers import evaluate as ev
        original = ev._refund_if_nothing_was_billed

        def spy(limiter, who, exc):
            seen["billed"] = getattr(exc, "completed_llm_calls", None)
            return original(limiter, who, exc)

        ev._refund_if_nothing_was_billed = spy
        try:
            r = c.post("/api/v1/evaluate", json={"text": policy_text})
        finally:
            ev._refund_if_nothing_was_billed = original
            pipeline._extract = real_extract

    assert r.status_code == 429
    assert seen["billed"] == 2, "both attempts billed a call; a refund here would be wrong"
