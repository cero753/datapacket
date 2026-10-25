"""MCP server exposing the de-identified company as tools. One process per episode;
submit() grades against the answer key and appends to runs/mcp_results.jsonl."""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .env import Store, grade, load_tasks

ROOT = Path(os.environ.get("DATAPACKET_ROOT", "out"))
RUNS = Path(os.environ.get("DATAPACKET_RUNS", "runs"))
store = Store(ROOT)
tasks = {t["task_id"]: t for t in load_tasks(ROOT)}
calls = {"n": 0}
mcp = FastMCP("company")


def _count():
    calls["n"] += 1


@mcp.tool()
def search_records(query: str, source: str | None = None, limit: int = 8) -> list[dict]:
    """Keyword search over emails, Slack, tickets and SOPs. source: email|slack|ticket|sop (optional)."""
    _count()
    return store.search(query, source, limit)


@mcp.tool()
def get_record(record_id: str) -> dict:
    """Full text and metadata of one record (e.g. EM-00012, SL-00450, TK-00031, SOP-07)."""
    _count()
    return store.get(record_id) or {"error": f"no record {record_id}"}


@mcp.tool()
def list_sops() -> list[dict]:
    """All standard operating procedures: id and title."""
    _count()
    return store.list_sops()


@mcp.tool()
def submit(task_id: str, amount: int, approver: str, sop: str) -> str:
    """Submit the final answer. Can be called once."""
    _count()
    t = tasks.get(task_id)
    if not t:
        return "unknown task id"
    rec = grade(t, amount, approver, sop, store.seen)
    rec.update(model=os.environ.get("DATAPACKET_MODEL", "unknown"), tool_calls=calls["n"],
               submitted={"amount": amount, "approver": approver, "sop": sop})
    RUNS.mkdir(parents=True, exist_ok=True)
    with open(RUNS / "mcp_results.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    return "submitted"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
