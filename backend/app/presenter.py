"""Raw pipeline output -> EvaluateResponse (_local/team.md section 6.7).

This is the privacy boundary. Every field of the response is constructed explicitly here, so
the internal keys (`history`, `batch_calls`, `shown`, `search_log` contents, `problems`,
`error`, raw LLM text, the dropped quotes themselves) cannot leak by being copied along.
"""
from __future__ import annotations

from datetime import datetime, timezone

import privascore
from privascore.extractor import PROMPT_VERSION
from privascore.scoring import SCORING_VERSION
from privascore.text import segment

from . import catalog
from .pipeline import RawAnalysis, utf16_offsets
from .schemas import (BertCategory, BertProfile, Document, Evidence, EvaluateResponse, FlagResult,
                      Meta, Metrics, Paragraph, Policy, Readability, Scores, VagueExample,
                      Vagueness, Warning_)

RATIONALE_STATUSES = {"verified", "verified_partial", "absent_unverifiable"}

WARNINGS = {
    "FEW_LINE_BREAKS": "The text has almost no line breaks, so section headings and the category "
                       "profile are less reliable. Paste it with its original line breaks if you can.",
    "NO_MATCHES": "None of the 16 practices matched anything in this text. Check that it is a "
                  "privacy policy.",
    "MOCK_PROVIDER": "Mock mode: these labels are placeholders, not a real analysis.",
    "BERT_UNAVAILABLE": "The category profile is unavailable on this server.",
}


def present(text: str, raw: RawAnalysis, pipeline, source: str = "live",
            company_name: str | None = None, document_text: str | None = None) -> EvaluateResponse:
    extraction, metrics = raw.extraction, raw.metrics
    u16 = utf16_offsets(text)
    paragraphs = segment(text)
    with_sentences = [p for p in paragraphs if p["sentences"]]
    sc = extraction["scores"]
    per_flag = {e["flag"]: e for e in sc["per_flag"]}

    flags = [_flag(f, extraction["flags"][f.id], per_flag[f.id], pipeline.rules, text, u16)
             for f in pipeline.flagset.flags]

    return EvaluateResponse(
        api_version="1",
        source=source,
        policy=Policy(company_name=(company_name or "").strip() or None,
                      scope=extraction["scope"], chars=len(text),
                      sentences=extraction["n_sentences"], paragraphs=len(with_sentences),
                      text_sha256=extraction["text_sha256"]),
        scores=Scores(risk_index=sc["risk_index"], risk_index_display=sc["risk_index_display"],
                      disclosure_quality=sc["disclosure_quality"],
                      disclosure_quality_display=sc["disclosure_quality_display"],
                      n_applicable=sc["n_applicable"], n_not_stated=sc["n_not_stated"],
                      complete=sc["complete"], rejected_flags=sc["rejected_flags_scored_as_UN"],
                      scoring_version=sc["scoring_version"]),
        flags=flags,
        metrics=_metrics(metrics, pipeline.bert_status),
        document=Document(paragraphs=[Paragraph(id=p["pid"], offset_utf16=(u16(p["start"]), u16(p["end"])),
                                                is_heading=p["is_heading"]) for p in paragraphs],
                          text=document_text),
        warnings=_warnings(text, flags, len(with_sentences), pipeline, metrics),
        meta=Meta(provider=pipeline.provider, model=raw.model or pipeline.model, prompt_version=PROMPT_VERSION,
                  rules_version=pipeline.rules["version"],
                  flag_definitions_version=pipeline.flagset.version,
                  privascore_version=privascore.__version__, llm_calls=raw.llm_calls,
                  timings_ms=raw.timings_ms,
                  analysed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )


def _flag(flag, result: dict, score: dict, rules: dict, text: str, u16) -> FlagResult:
    # A rejected flag has state None and is scored as UN (scoring.py already did that).
    state = result["state"] or "UN"
    status = result["status"]
    return FlagResult(
        id=flag.id, key=flag.key, title=catalog.title(flag.id), group=catalog.group(flag.id),
        type=flag.type, weight=flag.weight, question=flag.question,
        state=state, state_meaning=catalog.state_meaning(rules, flag.id, state), status=status,
        applicable=score["applicable"],
        not_applicable_reason=score["reason"] or None,
        risk_points=score["risk_points"], max_risk_points=score["max_risk_points"],
        quality_points=score["quality_points"],
        # The model's own reason. Suppressed for the statuses where the pipeline fills it with
        # internal boilerplate ("not applicable: AI1=UN") or where there was no answer at all.
        rationale=result.get("rationale") if status in RATIONALE_STATUSES else None,
        evidence=[Evidence(sentence_id=e["id"], heading=e.get("heading") or None, match=e["status"],
                           offset_utf16=(u16(e["start"]), u16(e["end"])),
                           # The policy's own characters: a "normalized" match means the model's
                           # quote string differs from the text (curly quotes, dashes, case).
                           text=text[e["start"]:e["end"]])
                  for e in result["evidence"]],
        # The count only. The failed quotes themselves are never sent.
        dropped_evidence_count=len(result.get("dropped_evidence") or []),
        # not_applicable records are built without a search at all, hence the defaults.
        n_candidates=result.get("n_candidates") or 0,
        n_search_terms=len(result.get("search_log") or {}),
    )


def _metrics(m: dict, bert_status: str) -> Metrics:
    v = m["vagueness"]
    b = m.get("bert_profile")
    return Metrics(
        readability=Readability(**m["readability"]),
        vagueness=Vagueness(vague_sentence_fraction=v["vague_sentence_fraction"],
                            multi_category_fraction=v["multi_category_fraction"],
                            cues_per_1000_words=v["cues_per_1000_words"],
                            examples=[VagueExample(sentence_id=e["sid"], text=e["text"],
                                                   cues=e["categories"]) for e in v["examples"]]),
        bert_profile=BertProfile(available=True, paragraphs=b["paragraphs"], threshold=0.5,
                                 categories=[BertCategory(name=n, share=s)
                                             for n, s in b["share"].items()])
        if b else BertProfile(available=False,
                                  # "disabled" (PRIVASCORE_BERT=off) or "unavailable" (load failed)
                                  reason="disabled" if bert_status == "disabled" else "unavailable"),
    )


def _warnings(text: str, flags: list[FlagResult], n_paragraphs: int, pipeline, metrics: dict):
    codes = []
    if n_paragraphs < 5 and len(text) > 5000:
        codes.append("FEW_LINE_BREAKS")
    if all(f.n_candidates == 0 for f in flags):
        codes.append("NO_MATCHES")
    if pipeline.provider == "mock":
        codes.append("MOCK_PROVIDER")
    if "bert_profile" not in metrics:
        codes.append("BERT_UNAVAILABLE")
    return [Warning_(code=c, message=WARNINGS[c]) for c in codes]
