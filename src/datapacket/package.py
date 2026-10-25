"""Assemble what a lab actually receives: the scrubbed corpus, the environment's
tasks (without answers), a red-team sample, a lineage manifest and a data card."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from collections import Counter
from pathlib import Path

from . import __version__


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def build(root: Path, results: Path | None = None) -> Path:
    pkt = root / "packet"
    pkt.mkdir(exist_ok=True)
    shutil.copy(root / "deid" / "corpus.jsonl", pkt / "corpus.jsonl")
    report = json.loads((root / "deid" / "report.json").read_text())
    tasks = json.loads((root / "groundtruth" / "tasks.json").read_text())
    (pkt / "tasks.jsonl").write_text("".join(
        json.dumps({"task_id": t["task_id"], "tier": t["tier"], "ticket_id": t["ticket_id"]}) + "\n" for t in tasks))
    docs = [json.loads(l) for l in (pkt / "corpus.jsonl").read_text(encoding="utf-8").splitlines()]
    rng = random.Random(0)
    (pkt / "redteam_sample.jsonl").write_text(
        "".join(json.dumps(d) + "\n" for d in rng.sample(docs, 200)), encoding="utf-8")
    raw = root / "raw"
    manifest = {
        "pipeline_version": __version__,
        "inputs": {p.name: _sha(p) for p in sorted(raw.iterdir())},
        "outputs": {p.name: _sha(p) for p in sorted(pkt.iterdir()) if p.suffix == ".jsonl"},
        "records_by_source": dict(Counter(d["source"] for d in docs)),
        "steps": ["ingest (one connector per source)", "identity graph (directory + CRM)",
                  "de-id: patterns -> directory aliases -> NER (local, no hosted LLM)",
                  "task build: ticket -> change-order resolution with answer key held back"],
    }
    (pkt / "manifest.json").write_text(json.dumps(manifest, indent=1))
    rates = ""
    if results and results.exists():
        rows = [json.loads(l) for l in results.read_text().splitlines()]
        by = {}
        for r in rows:
            by.setdefault((r["model"], r["tier"]), []).append(r["passed"])
        rates = "\n".join(f"| {m} | {t} | {sum(v)}/{len(v)} |" for (m, t), v in sorted(by.items()))
        rates = "\n## Model pass rates\n\n| model | tier | passed |\n|---|---|---|\n" + rates + "\n"
    bt = report["by_type"]
    card = f"""# Data card: Halvorsen & Pike Architects (synthetic demo)

**What it is.** {report['records']:,} de-identified records (email, Slack, client tickets, SOPs) from a
200-person architecture firm, plus {len(tasks)} verifiable agent tasks built from real ticket-to-resolution
paths. This demo firm is synthetic so that the PII ground truth is known exactly.

## De-identification (measured, not claimed)

- Planted PII items: {report['planted_pii']:,}. Recall **{report['recall']:.2%}**, precision **{report['precision']:.2%}**.
- Structured identifiers (email, phone, SSN, employee ID, address, handle): {min(bt[k]['recall'] for k in ('EMAIL','PHONE','SSN','EMPLOYEE_ID','ADDRESS','HANDLE')):.0%} recall.
- Known people (employees and client contacts, every nickname): {bt['PERSON']['recall']:.2%}.
- People in no directory (inspectors, neighbours): {bt['PERSON_UNLISTED']['recall']:.2%}, caught by the NER layer.
- Identity linkage: {report['person_linkage']['accuracy']:.1%} of person mentions mapped to the right pseudonym;
  the rest are redacted but left unlinked when a bare first name is ambiguous.
- Known residual risk: short nicknames that are also English words ("Will", "Drew") at sentence start.
  These go to human review, along with a random sample.
- The pseudonym key is held by the seller-side pipeline and never ships.

## Environment

Each task is a client ticket asking for a change order's approved amount, approver and governing SOP.
Medium tasks have a superseded quote; hard tasks add a stale approval, a near-duplicate CO number on
another project, and a prompt injection inside an email. Reward is exact match on all three fields and is
zero unless the agent retrieved a record containing the evidence.
{rates}
## Lineage

Input and output hashes are in `manifest.json`. `redteam_sample.jsonl` holds 200 random records for the
buyer to attack for re-identification before purchase.
"""
    (pkt / "DATACARD.md").write_text(card, encoding="utf-8")
    return pkt
