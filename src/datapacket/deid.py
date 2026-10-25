"""De-identification in three layers, cheapest first:

1. deterministic patterns: emails, phones, SSNs, employee IDs, street addresses, @handles
2. directory matching through the identity graph: every name and nickname of every
   known employee and client contact, mapped to a stable pseudonym
3. statistical NER (Presidio + spaCy, optional): people who are in no directory,
   like an inspector or a neighbour mentioned once

Runs fully local. Raw seller data should never be sent to a hosted LLM for this step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .identity import IdentityGraph

PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "PHONE": re.compile(r"\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "EMPLOYEE_ID": re.compile(r"\bHP-\d{5}\b"),
    "ADDRESS": re.compile(r"\b\d{2,5} [A-Z][a-z]+ (?:Ave|Ln|Rd|Dr|St|Way|Ct|Blvd)\b,? [A-Z][a-zA-Z ]+, [A-Z]{2} \d{5}\b"),
    "HANDLE": re.compile(r"(?<=@)[a-z][a-z0-9]{2,}\b"),
}


_CODE = re.compile(r"[A-Z]{1,3}-\d+|\d")


@dataclass
class Span:
    start: int
    end: int
    type: str
    layer: str
    pid: str | None = None


class Scrubber:
    def __init__(self, graph: IdentityGraph, ner: bool = False, keep_terms: list[str] = ()):
        self.g = graph
        # business vocabulary the seller supplies (project and client names) that NER
        # would otherwise mistake for people; codes like CO-1234 or A-9 are never names
        self.keep = set(keep_terms)
        self.ext: dict[str, str] = {}
        self.analyzer = None
        if ner:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            nlp = NlpEngineProvider(nlp_configuration={
                "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_md"}]
            }).create_engine()
            self.analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])

    def detect(self, text: str, context: set[str]) -> list[Span]:
        spans: list[Span] = []
        for typ, rx in PATTERNS.items():
            for m in rx.finditer(text):
                if typ == "HANDLE" and not self.g.lookup(m.group()):
                    continue
                spans.append(Span(m.start(), m.end(), typ, "pattern", self.g.lookup(m.group())))
        for s, e, name in self.g.find_names(text):
            spans.append(Span(s, e, "PERSON", "directory", self.g.resolve(name, context)))
        if self.analyzer:
            for r in self.analyzer.analyze(text=text, language="en", entities=["PERSON"], score_threshold=0.6):
                frag = text[r.start:r.end]
                if "PERSON_" in frag or "\n" in frag or _CODE.search(frag) \
                        or any(frag in k for k in self.keep):
                    continue
                spans.append(Span(r.start, r.end, "PERSON", "ner"))
        return _merge(spans)

    def replacement(self, sp: Span, original: str) -> str:
        ps = self.g.pseudo.get(sp.pid) if sp.pid else None
        if sp.type == "PERSON":
            if ps:
                return ps
            key = original.strip()
            if key not in self.ext:
                self.ext[key] = f"EXT_PERSON_{len(self.ext) + 1:04d}"
            return self.ext[key]
        if sp.type == "EMAIL":
            return f"{ps.lower()}@redacted.example" if ps else "[EMAIL]"
        if sp.type == "HANDLE":
            return ps if ps else "[HANDLE]"
        return f"[{sp.type}]"

    def scrub(self, text: str, context: set[str]) -> tuple[str, list[Span]]:
        spans = self.detect(text, context)
        out, pos = [], 0
        for sp in spans:
            out.append(text[pos:sp.start])
            out.append(self.replacement(sp, text[sp.start:sp.end]))
            pos = sp.end
        out.append(text[pos:])
        return "".join(out), spans

    def scrub_meta(self, meta: dict) -> dict:
        def one(v):
            pid = self.g.lookup(v)
            if not pid:
                return "[REDACTED]"
            ps = self.g.pseudo[pid]
            return f"{ps.lower()}@redacted.example" if "@" in v else ps
        out = {}
        for k, v in meta.items():
            if k in ("from", "requester", "assignee", "user"):
                out[k] = one(v)
            elif k == "to":
                out[k] = [one(x) for x in v]
            else:
                out[k] = v
        return out


def _merge(spans: list[Span]) -> list[Span]:
    """Resolve overlaps: keep the longest span; prefer ones that carry a linked identity."""
    spans.sort(key=lambda s: (s.start, -(s.end - s.start), s.pid is None))
    out: list[Span] = []
    for sp in spans:
        if out and sp.start < out[-1].end:
            last = out[-1]
            if sp.end > last.end:
                last.end = sp.end
            if last.pid is None and sp.pid:
                last.pid = sp.pid
            continue
        out.append(sp)
    return out


def context_pids(graph: IdentityGraph, meta: dict) -> set[str]:
    ids = [meta.get(k) for k in ("from", "user", "requester", "assignee")] + list(meta.get("to", []))
    return {p for p in (graph.lookup(i) for i in ids if i) if p}
