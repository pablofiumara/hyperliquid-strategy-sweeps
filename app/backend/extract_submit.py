#!/usr/bin/env python3
"""The full deliverable from a `cline --json` run transcript.

cline's styled output ellipsizes long tool payloads, so a run's complete
answer only survives in the JSON event stream: either as the
submit_and_exit summary (the tool call carries it verbatim) or, failing
that, as the agent's final text message. Prints the deliverable as-is, or
nothing when there is none.

Usage: cline --json ... > transcript.json ; python3 extract_submit.py transcript.json
"""
import json
import re
import sys


def main() -> None:
    if len(sys.argv) < 2:
        return
    summary = None
    texts: list[str] = []
    with open(sys.argv[1], errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            ev = e.get("event") or {}
            if ev.get("type") == "content_start" and ev.get("toolName") == "submit_and_exit":
                s = (ev.get("input") or {}).get("summary")
                if isinstance(s, str) and s.strip():
                    summary = s
            elif ev.get("type") == "content_end" and ev.get("contentType") == "text":
                t = ev.get("text")
                if isinstance(t, str) and t.strip():
                    texts.append(t)
    out = summary or "\n\n".join(texts)
    out = _strip_boilerplate(out)
    if out.strip():
        sys.stdout.write(out)


# Agent housekeeping that models like to append around the deliverable.
_BOILER = re.compile(
    r"^(verified complete\.?|no files were created or modified.*"
    r"|submission recorded.*|answer submitted\.?)$",
    re.IGNORECASE,
)

# Report-style meta clauses some models wrap around the actual answer:
# a leading "Answered ... :"/"Reviewed ... ." framing and a trailing
# "The answer cites .../no files created" wrap-up. Only stripped when they
# sit exactly at the start/end, so substantive text is never cut.
_META_LEAD = re.compile(
    r"^(?:answered|reviewed|reviewing|based on|the question asks"
    r"|the answer (?:cites|is based|draws|uses)|respuesta[^:.]{0,80}"
    r"|la respuesta)[^:.]{0,100}[.:]\s*",
    re.IGNORECASE,
)
_META_TAIL = re.compile(
    r"\s+(?:the answer cites[^.]*|no files (?:were )?(?:created|modified)[^.]*"
    r"|verified complete|answer submitted)\.?\s*$",
    re.IGNORECASE,
)


def _strip_boilerplate(text: str) -> str:
    out = text
    for _ in range(4):  # meta clauses can chain; peel until stable
        before = out
        lines = [ln for ln in out.splitlines() if not _BOILER.match(ln.strip())]
        out = _META_LEAD.sub("", "\n".join(lines).strip(), count=1)
        out = _META_TAIL.sub("", out, count=1).strip()
        if out == before:
            break
    return out + "\n" if out else ""


if __name__ == "__main__":
    main()
