"""Ingest -> identity -> de-identify -> score. Writes the scrubbed corpus plus a
report that says, per PII type and per layer, what was caught and what leaked."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from .deid import Scrubber, context_pids
from .identity import IdentityGraph

SOURCES = ("email", "slack", "ticket", "sop")


# one connector per source system; each maps its native shape onto the common record
def _email(d):  return {**d, "participants": [d["meta"]["from"], *d["meta"]["to"]]}
def _slack(d):  return {**d, "participants": [d["meta"]["user"]]}
def _ticket(d): return {**d, "participants": [d["meta"]["requester"], d["meta"]["assignee"]]}
def _sop(d):    return {**d, "participants": []}


CONNECTORS = {"email": _email, "slack": _slack, "ticket": _ticket, "sop": _sop}


def ingest(raw: Path) -> list[dict]:
    recs = []
    for src in SOURCES:
        with open(raw / f"{src}.jsonl", encoding="utf-8") as f:
            recs += [CONNECTORS[src](json.loads(l)) for l in f]
    return recs


def run(root: Path, ner: bool = True) -> dict:
    raw, out = root / "raw", root / "deid"
    out.mkdir(parents=True, exist_ok=True)
    directory = json.loads((raw / "directory.json").read_text())
    graph = IdentityGraph(directory)
    projects = json.loads((raw / "projects.json").read_text())
    keep = [p["name"] for p in projects] + [p["client"] for p in projects]
    scrub = Scrubber(graph, ner=ner, keep_terms=keep)
    recs = ingest(raw)
    t0 = time.time()
    results = {}
    with open(out / "corpus.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            ctx = context_pids(graph, r["meta"])
            text, spans = scrub.scrub(r["text"], ctx)
            results[r["id"]] = spans
            f.write(json.dumps({"id": r["id"], "source": r["source"], "ts": r["ts"],
                                "meta": scrub.scrub_meta(r["meta"]), "text": text}) + "\n")
    elapsed = time.time() - t0
    report = score(root, results, graph, recs)
    report["records"] = len(recs)
    report["seconds"] = round(elapsed, 1)
    report["ner"] = ner
    (out / "report.json").write_text(json.dumps(report, indent=1))
    # the pid -> pseudonym map is the re-identification key: kept apart from the packet
    (root / "groundtruth" / "pseudonym_map.json").write_text(json.dumps(graph.pseudo, indent=1))
    return report


def score(root: Path, results: dict, graph: IdentityGraph, recs: list[dict]) -> dict:
    truth = {}
    with open(root / "groundtruth" / "pii_spans.jsonl", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            truth[d["id"]] = d["pii"]
    texts = {r["id"]: r["text"] for r in recs}
    by_type = defaultdict(Counter)
    caught_by = Counter()
    link = Counter()
    fp_examples, leak_examples = [], []
    fp = 0
    for rid, planted in truth.items():
        spans = results[rid]
        for p in planted:
            cov = [s for s in spans if s.start <= p["start"] and s.end >= p["end"]]
            kind = p["type"] + ("" if p["type"] != "PERSON" or p["entity"] else "_UNLISTED")
            by_type[kind]["total"] += 1
            if cov:
                by_type[kind]["caught"] += 1
                caught_by[cov[0].layer] += 1
                if p["type"] == "PERSON" and p["entity"]:
                    link["total"] += 1
                    link["correct"] += cov[0].pid == p["entity"]
                    link["unlinked"] += cov[0].pid is None
            elif len(leak_examples) < 15:
                leak_examples.append({"id": rid, "type": kind, "value": p["value"]})
        for s in spans:
            if not any(s.start < p["end"] and s.end > p["start"] for p in planted):
                fp += 1
                if len(fp_examples) < 15:
                    fp_examples.append({"id": rid, "layer": s.layer, "text": texts[rid][s.start:s.end]})
    total = sum(c["total"] for c in by_type.values())
    caught = sum(c["caught"] for c in by_type.values())
    redactions = sum(len(v) for v in results.values())
    return {
        "planted_pii": total,
        "recall": round(caught / total, 4),
        "precision": round((redactions - fp) / redactions, 4) if redactions else 1.0,
        "false_positives": fp,
        "by_type": {k: {**v, "recall": round(v["caught"] / v["total"], 4)} for k, v in sorted(by_type.items())},
        "caught_by_layer": dict(caught_by),
        "person_linkage": {**link, "accuracy": round(link["correct"] / link["total"], 4) if link["total"] else None},
        "leak_examples": leak_examples,
        "false_positive_examples": fp_examples,
    }
