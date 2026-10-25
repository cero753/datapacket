"""Identity graph: fold every way a person shows up (full name, nickname, "Joe D.",
email, phone, Slack handle, employee ID) onto one canonical ID, then into one
stable pseudonym. This is what keeps a de-identified packet useful: PERSON_0412
in an email is the same PERSON_0412 who approved in Slack and owns the ticket."""

from __future__ import annotations

import hashlib
import re

from .names import NICKNAMES, AMBIGUOUS

# Words that, right after an ambiguous alias at sentence start, mean it is not a name:
# "Will you...", "Drew a markup", "Pat the cache".
_NOT_NAME_NEXT = {"you", "the", "a", "an", "be", "we", "it", "this", "that", "there", "your", "they",
                  "i", "our", "my", "me", "up", "out", "on", "in"}


class IdentityGraph:
    def __init__(self, directory: list[dict], salt: str = "datapacket"):
        self.people = {p["pid"]: p for p in directory}
        order = sorted(self.people, key=lambda pid: hashlib.sha256((salt + pid).encode()).hexdigest())
        self.pseudo = {pid: f"PERSON_{i + 1:04d}" for i, pid in enumerate(order)}
        self.exact: dict[str, str] = {}  # identifier -> pid (unique keys only)
        self.alias: dict[str, set[str]] = {}  # name string -> candidate pids
        for pid, p in self.people.items():
            for k in (p["email"], p["phone"], p.get("handle"), p.get("employee_id")):
                if k:
                    self.exact[k.lower()] = pid
            names = [p["first"]] + NICKNAMES.get(p["first"], [])
            for n in names:
                self._add(n, pid)
                self._add(f"{n} {p['last']}", pid)
                self._add(f"{n} {p['last'][0]}.", pid)
        # longest first so "Joe Marlowe" wins over "Joe"
        self._alias_re = re.compile(
            r"(?<![\w@.])(" + "|".join(re.escape(a) for a in sorted(self.alias, key=len, reverse=True))
            + r")(?![\w])")

    def _add(self, key: str, pid: str):
        self.alias.setdefault(key, set()).add(pid)

    def lookup(self, identifier: str) -> str | None:
        return self.exact.get(identifier.lower().lstrip("@"))

    def resolve(self, name: str, context: set[str]) -> str | None:
        """Pick the person a name refers to. Unique alias wins; otherwise prefer someone
        already in the conversation (sender, recipients, channel author)."""
        cands = self.alias.get(name, set())
        if len(cands) == 1:
            return next(iter(cands))
        inctx = cands & context
        if len(inctx) == 1:
            return next(iter(inctx))
        return None  # ambiguous: still redacted, but not linked

    def find_names(self, text: str) -> list[tuple[int, int, str]]:
        out = []
        for m in self._alias_re.finditer(text):
            name = m.group(1)
            first = name.split()[0]
            if first in AMBIGUOUS and " " not in name:
                before = text[:m.start()].rstrip()
                at_start = before == "" or before[-1] in ".!?\n"
                nxt = re.match(r"\s+([A-Za-z']+)", text[m.end():])
                if at_start and nxt and nxt.group(1).lower() in _NOT_NAME_NEXT:
                    continue
                if not at_start and nxt and nxt.group(1)[0].islower() and before[-1:] not in ",:(" \
                        and not re.search(r"(Hi|Hey|morning|Thanks|with|to|and|ask|Ask|from|told|ping|Ping|for)$", before):
                    continue
            out.append((m.start(), m.end(), name))
        return out
