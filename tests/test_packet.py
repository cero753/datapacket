import json
import re
from pathlib import Path

import pytest

from datapacket.deid import Scrubber
from datapacket.env import Store, grade, load_tasks
from datapacket.identity import IdentityGraph
from datapacket.pipeline import run
from datapacket.synth import generate


@pytest.fixture(scope="module")
def packet(tmp_path_factory):
    root = tmp_path_factory.mktemp("pk")
    firm = generate(root)
    report = run(root, ner=False)
    return root, firm, report


def test_generation_is_deterministic(tmp_path):
    a = generate(tmp_path / "a")
    b = generate(tmp_path / "b")
    assert [r.text for r in a.records] == [r.text for r in b.records]


def test_planted_spans_match_text(packet):
    _, firm, _ = packet
    for rec in firm.records:
        for p in rec.pii:
            assert rec.text[p["start"]:p["end"]] == p["value"]


def test_identifiers_are_never_real(packet):
    _, firm, _ = packet
    assert all(p.ssn.startswith("9") for p in firm.people)  # 9xx area is never issued
    assert all("555-" in p.phone for p in firm.people + firm.clients)


def test_structured_pii_fully_removed(packet):
    root, firm, report = packet
    for t in ("EMAIL", "PHONE", "SSN", "EMPLOYEE_ID", "ADDRESS", "HANDLE"):
        assert report["by_type"][t]["recall"] == 1.0, t
    corpus = (root / "deid" / "corpus.jsonl").read_text()
    for p in firm.people[:50]:
        assert p.email not in corpus and p.phone not in corpus and p.ssn not in corpus


def test_known_people_recall_and_precision(packet):
    _, _, report = packet
    assert report["by_type"]["PERSON"]["recall"] >= 0.99
    assert report["precision"] >= 0.99


def test_unlisted_people_need_ner(packet):
    # honest baseline: without the NER layer, people in no directory leak
    _, _, report = packet
    assert report["by_type"]["PERSON_UNLISTED"]["recall"] < 0.05


def test_ambiguous_aliases(packet):
    root, _, _ = packet
    g = IdentityGraph(json.loads((root / "raw" / "directory.json").read_text()))
    s = Scrubber(g)
    assert "Will you" in s.scrub("Will you update the log?", set())[0]
    assert "Drew a markup" in s.scrub("Drew a markup of the matrix.", set())[0]
    if "Will" in g.alias:
        assert "Will" not in s.scrub("Thanks, Will", set())[0]


def test_nickname_and_full_name_link_to_one_pseudonym(packet):
    root, _, _ = packet
    g = IdentityGraph(json.loads((root / "raw" / "directory.json").read_text()))
    s = Scrubber(g)
    a = s.scrub("Joseph Marlowe approved it.", set())[0]
    b = s.scrub("Joe Marlowe approved it.", set())[0]
    c = s.scrub("Joe D. approved it.", {"E0000"})[0]
    assert a.split()[0] == b.split()[0] == c.split()[0] == g.pseudo["E0000"]


def test_pseudonym_key_kept_out_of_packet(packet):
    root, _, _ = packet
    assert not (root / "deid" / "pseudonym_map.json").exists()
    assert (root / "groundtruth" / "pseudonym_map.json").exists()


# ---------- verifier red team ----------
@pytest.fixture(scope="module")
def hard(packet):
    root, _, _ = packet
    t = next(x for x in load_tasks(root) if x["tier"] == "hard")
    return t, set(t["evidence"])


def test_correct_answer_with_evidence(hard):
    t, seen = hard
    a = t["answer"]
    assert grade(t, a["amount"], a["approver"], a["sop"], seen)["passed"]


def test_formatting_tolerance_is_not_a_hack(hard):
    t, seen = hard
    a = t["answer"]
    r = grade(t, f"${a['amount']:,}", a["approver"].lower(), a["sop"].lower(), seen)
    assert r["passed"]


def test_guess_without_reading_scores_zero(hard):
    t, _ = hard
    a = t["answer"]
    r = grade(t, a["amount"], a["approver"], a["sop"], set())
    assert r["reward"] == 0 and not r["passed"]


def test_hedged_amount_rejected(hard):
    t, seen = hard
    a = t["answer"]
    r = grade(t, f"{a['amount']} or {a['amount'] + 1500}", a["approver"], a["sop"], seen)
    assert not r["amount_ok"] and not r["passed"]


def test_listing_several_approvers_rejected(hard):
    t, seen = hard
    a = t["answer"]
    r = grade(t, a["amount"], f"{a['approver']}, PERSON_0001", a["sop"], seen)
    assert not r["approver_ok"]


def test_following_injection_fails_and_is_flagged(hard):
    t, seen = hard
    r = grade(t, 1, "PERSON_0001", t["answer"]["sop"], seen)
    assert r["injection_followed"] and not r["passed"]


def test_stale_first_quote_fails(packet):
    root, _, _ = packet
    store = Store(root)
    t = next(x for x in load_tasks(root) if x["tier"] == "medium")
    hits = store.search(t["co"])
    amounts = {int(m.replace(",", "")) for h in hits for m in re.findall(r"\$([\d,]+)", store.docs[h["id"]]["text"])}
    stale = [x for x in amounts if x != t["answer"]["amount"]]
    assert stale, "medium tasks must contain a superseded number"
    a = t["answer"]
    assert not grade(t, stale[0], a["approver"], a["sop"], set(t["evidence"]))["passed"]
