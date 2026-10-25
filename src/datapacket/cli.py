import argparse
import json
from pathlib import Path

from . import package, pipeline, synth


def main():
    ap = argparse.ArgumentParser(prog="datapacket")
    ap.add_argument("command", choices=["generate", "deid", "package", "all"])
    ap.add_argument("--out", default="out")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-ner", action="store_true")
    a = ap.parse_args()
    root = Path(a.out)
    if a.command in ("generate", "all"):
        f = synth.generate(root, a.seed)
        print(f"generated {len(f.records)} records, {len(f.tasks)} tasks -> {root / 'raw'}")
    if a.command in ("deid", "all"):
        r = pipeline.run(root, ner=not a.no_ner)
        print(json.dumps({k: r[k] for k in ("planted_pii", "recall", "precision", "person_linkage", "seconds")}, indent=1))
    if a.command in ("package", "all"):
        p = package.build(root, Path("runs/results.jsonl"))
        print(f"packet -> {p}")


if __name__ == "__main__":
    main()
