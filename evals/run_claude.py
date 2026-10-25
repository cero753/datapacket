"""Pass rates through Claude Code headless mode (uses your Claude login, no API key).

    uv run python evals/run_claude.py --models haiku sonnet --n 4

Each episode is a fresh `claude -p` with only the company MCP server (built-in tools
off, cwd outside the repo), so the agent can't read the answer key or the grader.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from datapacket.env import load_tasks, prompt  # noqa: E402

DATA = ROOT / "out"
RUNS = ROOT / "runs"


def episode(model: str, task: dict, timeout: int) -> dict:
    label = f"claude-code/{model}"
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="datapacket_"))
    env = {"DATAPACKET_ROOT": str(DATA), "DATAPACKET_RUNS": str(RUNS), "DATAPACKET_MODEL": label}
    (sandbox / "mcp.json").write_text(json.dumps({"mcpServers": {"company": {
        "command": "uv", "args": ["run", "--directory", str(ROOT), "--extra", "mcp", "datapacket-mcp"], "env": env}}}))
    log = RUNS / "mcp_results.jsonl"
    before = log.read_text().count("\n") if log.exists() else 0
    cmd = [shutil.which("claude") or "claude", "-p", prompt(task), "--model", model,
           "--mcp-config", str(sandbox / "mcp.json"), "--strict-mcp-config", "--tools", "",
           "--allowedTools", "mcp__company__*", "--output-format", "json"]
    try:
        p = subprocess.run(cmd, cwd=sandbox, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", env={**os.environ, **env})
        meta = json.loads(p.stdout or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        meta = {"error": type(e).__name__}
    lines = log.read_text().splitlines()[before:] if log.exists() else []
    mine = [json.loads(l) for l in lines]
    mine = [r for r in mine if r["model"] == label and r["task_id"] == task["task_id"]]
    rec = mine[-1] if mine else {"model": label, "task_id": task["task_id"], "tier": task["tier"],
                                 "reward": 0.0, "passed": False, "error": meta.get("error") or "no submit"}
    rec["turns"] = meta.get("num_turns")
    rec["cost_equiv_usd"] = meta.get("total_cost_usd")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["haiku", "sonnet"])
    ap.add_argument("--tiers", nargs="+", default=["easy", "medium", "hard"])
    ap.add_argument("--n", type=int, default=4, help="tasks per tier")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    RUNS.mkdir(exist_ok=True)
    out = RUNS / "results.jsonl"
    done = set()
    if out.exists():
        done = {(r["model"], r["task_id"]) for r in map(json.loads, out.read_text().splitlines()) if not r.get("error")}
    tasks = load_tasks(DATA)
    pick = [t for tier in a.tiers for t in [x for x in tasks if x["tier"] == tier][:a.n]]
    for m in a.models:  # sequential: parallel claude -p runs got OOM-killed on this box before
        for t in pick:
            if (f"claude-code/{m}", t["task_id"]) in done:
                continue
            r = episode(m, t, a.timeout)
            with out.open("a") as f:
                f.write(json.dumps(r) + "\n")
            print(f"{r['model']:20s} {t['tier']:6s} {t['task_id']} reward={r['reward']:.2f} "
                  f"passed={r['passed']} {r.get('error', '')}", flush=True)


if __name__ == "__main__":
    main()
