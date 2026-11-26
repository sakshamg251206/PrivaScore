"""The only place the backend touches privascore. Everything here is configuration or a thin wrapper."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace

from privascore.config import load_config
from privascore.extractor import Extractor, load_rules
from privascore.flags import load_flags
from privascore.llm import LLMError, QuotaExhausted, make_client
from privascore.metrics import policy_metrics

from .settings import Settings


class InMemoryExtractor(Extractor):
    """Identical extraction, but never reads or writes the on-disk LLM reply cache (.cache/llm/).

    Extractor._call(system, user) -> (reply_text, cached) is the only method that touches the
    cache, so overriding it is enough: no file is ever read or created.
    """

    def _call(self, system, user):
        resp = self.client.complete_json(system, user)
        self.stats["llm_calls"] += 1
        return resp.text, False


@dataclass
class RawAnalysis:
    extraction: dict      # Extractor.extract_policy_batch() output
    metrics: dict         # privascore.metrics.policy_metrics() output
    llm_calls: int
    timings_ms: dict
    model: str = ""       # which model actually answered; "" means the primary one


class PipelineService:
    """Built once in the FastAPI lifespan. Holds the LLM client (shared, so its min_interval
    throttle is global), the flag set, the prompt rules and the BERT model."""

    def __init__(self, settings: Settings):
        cfg = load_config(provider=settings.llm_provider or None, model=settings.llm_model or None)
        # Same as `python -m privascore.extract --batch`: one batch answer covers up to 16 flags.
        # Without this, replies get truncated and every flag ends up "rejected".
        cfg.llm.max_output_tokens = max(cfg.llm.max_output_tokens, cfg.extractor.batch_max_output_tokens)
        # Interactive use: fail fast instead of sleeping 65 s per rate-limit wait (the CLI default).
        cfg.llm.max_rate_limit_waits = settings.llm_max_rate_limit_waits
        cfg.llm.overload_waits = tuple(settings.llm_overload_waits)
        cfg.llm.max_http_retries = settings.llm_max_http_retries
        self.cfg = cfg
        self.provider, self.model = cfg.llm.provider, cfg.llm.model
        self.client = make_client(cfg.llm)       # raises LLMError if the API key is missing
        self.fallback_model = settings.llm_fallback_model.strip()
        self._fallback_client = None             # built on first use, not at startup
        self.flagset = load_flags()
        self.rules = load_rules()                # per-flag ED/CD/EE definitions, shown in the UI
        self.bert = None
        self.bert_status = "disabled"
        if settings.bert_enabled:
            try:
                from privascore.bert import OPP115Bert   # imports torch; only when BERT is on
                self.bert = OPP115Bert()
                self.bert_status = "loaded"
            except Exception as e:               # checkpoint missing, torch missing, ...
                if settings.bert_required:
                    raise RuntimeError(
                        f"BERT checkpoint could not be loaded ({type(e).__name__}). See section 4 of "
                        "_local/team.md, or set PRIVASCORE_BERT_REQUIRED=false."
                    ) from None
                self.bert_status = "unavailable"

    # --- blocking helpers, run in worker threads

    def _metrics(self, text: str):
        t = time.perf_counter()
        m = policy_metrics(text, self.bert)
        return m, round((time.perf_counter() - t) * 1000)

    def _fallback(self):
        """The fallback client, built on first use. A bad model name must not stop the server
        booting, and most requests never need it."""
        if self._fallback_client is None:
            self._fallback_client = make_client(replace(self.cfg.llm, model=self.fallback_model))
        return self._fallback_client

    def _extract(self, text: str, scope: str, company_name: str | None, client=None):
        t = time.perf_counter()
        ex = InMemoryExtractor(client or self.client, self.flagset, self.cfg.extractor)   # cheap; one per request
        try:
            res = ex.extract_policy_batch(text, policy_id="input", scope=scope,
                                          policy_name=(company_name or "").strip().lower())
        except LLMError as exc:
            # How many provider calls COMPLETED before this failed. The counter is incremented
            # only once a call returns, so this is exactly the number the provider billed, and
            # the route refunds the request's budget charge only when it is zero. A batch
            # extraction retries once, so a 503 can arrive after a first call that did succeed.
            exc.completed_llm_calls = ex.stats["llm_calls"]
            raise
        return res, ex.stats["llm_calls"], round((time.perf_counter() - t) * 1000)

    # --- async entry point used by the route

    async def analyse(self, text: str, scope: str, company_name: str | None) -> RawAnalysis:
        t = time.perf_counter()
        metrics_task = asyncio.ensure_future(asyncio.to_thread(self._metrics, text))
        try:
            try:
                extraction, calls, e_ms = await asyncio.to_thread(
                    self._extract, text, scope, company_name)
                model = self.model
            except QuotaExhausted as primary:
                # The provider's cap is per model, so a different model may still have quota.
                # Only tried when one is configured; otherwise this is the old behaviour.
                if not self.fallback_model:
                    raise
                spent = getattr(primary, "completed_llm_calls", 0)
                try:
                    extraction, calls, e_ms = await asyncio.to_thread(
                        self._extract, text, scope, company_name, self._fallback())
                except LLMError as second:
                    # Both failed. The route refunds only when NOTHING was billed, so the
                    # count has to cover both attempts, not just the second one.
                    second.completed_llm_calls = spent + getattr(second, "completed_llm_calls", 0)
                    raise
                calls += spent
                model = self.fallback_model
        except BaseException:
            metrics_task.cancel()                # nothing will await it otherwise
            raise
        metrics, m_ms = await metrics_task
        total = round((time.perf_counter() - t) * 1000)
        return RawAnalysis(extraction, metrics, calls,
                           {"metrics": m_ms, "extraction": e_ms, "total": total}, model=model)


def utf16_offsets(text: str):
    """Python indexes code points; JavaScript indexes UTF-16 code units. Returns a function
    mapping a Python offset to a JS offset. Identity when the text has no astral characters."""
    if not any(ord(c) > 0xFFFF for c in text):
        return lambda i: i
    prefix = [0] * (len(text) + 1)
    for k, c in enumerate(text):
        prefix[k + 1] = prefix[k] + (2 if ord(c) > 0xFFFF else 1)
    return prefix.__getitem__
