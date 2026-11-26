"""POST /api/v1/evaluate: one blocking analysis of pasted text.

The text exists only in this function's locals and in the worker threads it starts. Nothing is
written to disk, logged or cached.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response

from privascore.llm import LLMError, ProviderOverloaded, QuotaExhausted

from ..errors import ApiError
from ..limits import client_identity, run_guarded
from ..presenter import present
from ..schemas import EvaluateRequest, EvaluateResponse

router = APIRouter()


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(body: EvaluateRequest, request: Request, response: Response) -> EvaluateResponse:
    s = request.app.state.settings
    pipeline = request.app.state.pipeline
    gate = request.app.state.gate

    # The frontend normalises line endings the same way before sending. Offsets in the response
    # refer to THIS string, so the backend must not change the text in any other way.
    text = body.text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text.strip()) < s.min_chars:
        raise ApiError("TEXT_TOO_SHORT", 422)
    if len(text) > s.max_chars:
        raise ApiError("TEXT_TOO_LONG", 422)

    # BUSY is decided first, and deliberately so. The limiter's budget exists to bound what is
    # spent at the provider; a request refused here never reaches it. Charging those would let
    # anyone exhaust the day's budget with rapid requests that cost the key nothing, which is a
    # denial of service against the guard itself. Neither check awaits, so nothing can slip in
    # between them.
    if gate.locked():
        raise ApiError("BUSY", 429, retry_after_s=30)

    limiter = request.app.state.rate_limiter
    who = None
    if limiter.enabled:
        who = client_identity(request.client.host if request.client else "unknown",
                              request.headers, s.trust_proxy, s.trusted_proxy_hops)
        wait_s = limiter.check(who)
        if wait_s is not None:
            raise ApiError("RATE_LIMITED", 429, retry_after_s=max(1, int(wait_s)))
    # NOT `async with gate`: the analysis runs in threads that cannot be cancelled, so a client
    # that disconnects would release the permit while its Gemini call was still in flight.
    # run_guarded releases on the work finishing, not on this request finishing.
    try:
        raw = await run_guarded(gate, pipeline.analyse(text, body.scope, body.company_name))
    except ProviderOverloaded as exc:            # subclass of QuotaExhausted: catch it FIRST
        _refund_if_nothing_was_billed(limiter, who, exc)
        raise ApiError("LLM_OVERLOADED", 503, retry_after_s=120) from None
    except QuotaExhausted as exc:
        _refund_if_nothing_was_billed(limiter, who, exc)
        # No Retry-After: this is reached on a *daily* provider cap (base.py raises it at once on a
        # "per day" 429), which resets hours away, not in a minute. A short hint here was a wrong
        # promise -- the provider's own retryDelay has been ~18h. We are not told the real figure
        # (and must not forward provider text), so we send none rather than invent one.
        raise ApiError("LLM_QUOTA", 429) from None
    except LLMError:
        # Most LLMErrors are absorbed inside the pipeline (those flags become "rejected" and
        # the result is a 200 with complete=false). Only an escaping one lands here.
        raise ApiError("LLM_ERROR", 502) from None

    response.headers["Cache-Control"] = "no-store"
    return present(text, raw, pipeline, source="live", company_name=body.company_name)


def _refund_if_nothing_was_billed(limiter, who: str | None, exc: Exception) -> None:
    """Hand the budget charge back only when the provider provably billed nothing.

    The budget bounds provider spend, so an attempt refused outright must not eat the day's
    allowance. But a batch extraction retries once, so a 503 can follow a first call that did
    succeed and was billed. The pipeline records how many calls completed; absent that
    attribute, assume the worst and keep the charge.
    """
    if who is None:
        return
    if getattr(exc, "completed_llm_calls", None) == 0:
        limiter.refund(who)
