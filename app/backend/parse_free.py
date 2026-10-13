#!/usr/bin/env python3
"""Parse `kilo models --verbose` / `opencode models --verbose` and print free model ids.

Usage: <tool> models --verbose | parse_free.py {kilo|opencode}

A model is free only when NOTHING about it costs money, so the cost object is
checked in full -- input, output and both cache directions. A model flagged
free by the vendor but with a non-zero cache write would still bill us, and
this driver's whole contract is "$0 or it does not run".

kilo      -> the CLI's own "isFree" flag is true AND every cost field is 0
opencode  -> every cost field is 0 (input, output, cache read, cache write)

cline is intentionally NOT parsed here: its CLI has no models listing, so its
free list is fetched from the HTTP API instead (api.cline.bot recommended-
models, .free[] ids, via curl+jq) -- see load_free_lists() in run-models.sh.
Cline's payload carries no prices, so cline relies on the probe stage alone.
"""
import json
import re
import sys

TOOL = sys.argv[1] if len(sys.argv) > 1 else "kilo"
PREFIX = TOOL + "/"


def zero_cost(model):
    """True only when the model cannot bill us: every priced field is 0."""
    cost = model.get("cost") or {}
    cache = cost.get("cache") or {}
    return (
        cost.get("input") == 0
        and cost.get("output") == 0
        and cache.get("read", 0) == 0
        and cache.get("write", 0) == 0
    )


def is_free(model):
    if not zero_cost(model):
        return False
    if TOOL == "kilo":
        # Trust the CLI's own flag too: a zero-cost model the provider does
        # not advertise as free is not one we should be spending calls on.
        return model.get("isFree") is True
    return True


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
