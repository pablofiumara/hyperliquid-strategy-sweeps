#!/usr/bin/env python3
"""Parse `kilo models --verbose` / `opencode models --verbose` and print free model ids.

Usage: <tool> models --verbose | parse_free.py {kilo|opencode}

kilo      -> free means the CLI's own "isFree" flag is true
opencode  -> free means input and output cost are both 0

cline is intentionally NOT parsed here: its CLI has no models listing, so its
free list is fetched from the HTTP API instead (api.cline.bot recommended-
models, .free[] ids, via curl+jq) -- see load_free_lists() in run-models.sh.
"""
import json
import re
import sys

TOOL = sys.argv[1] if len(sys.argv) > 1 else "kilo"
PREFIX = TOOL + "/"


def is_free(model):
    if TOOL == "kilo":
        return model.get("isFree") is True
    cost = model.get("cost") or {}
    return cost.get("input") == 0 and cost.get("output") == 0


def main():
    cur, buf, out = None, [], []
    for line in sys.stdin.read().split("\n"):
        if re.match(r"^%s\S+$" % re.escape(PREFIX), line):
            if cur and buf:
                try:
                    if is_free(json.loads("\n".join(buf))):
                        out.append(cur)
                except Exception:
                    pass
            cur, buf = line, []
        elif cur is not None:
            buf.append(line)
    if cur and buf:
        try:
            if is_free(json.loads("\n".join(buf))):
                out.append(cur)
        except Exception:
            pass
    print("\n".join(sorted(set(out))))


if __name__ == "__main__":
    main()
