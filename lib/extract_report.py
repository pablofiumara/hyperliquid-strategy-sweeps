#!/usr/bin/env python3
"""strategy_report.md = the strategy description in EVERY model folder.

One canonical filename everywhere. Source priority per run dir:
  1. work/*.md  -- the agent wrote its own report; content is MOVED here
                   (original deleted: one fact, one file).
  2. wallet.txt -- legacy extract from sweep #1; body is MIGRATED here.
  3. output.txt -- trailing final-answer prose is extracted (cline agents
                   without a report, kilo/opencode runs).
Runs with no answer get a `NO STRATEGY — ...` flag instead.

After this runs: every run dir has strategy_report.md, and neither wallet.txt
nor work/*.md remain (dedup: single deliverable per dir). Probe transients
(probe.txt) are removed too: the verdict lives in meta.json's "probe" field
and the full transcript in output.txt.

Layout: <root>/<wallet-address>/<model-label>/...  -- this script walks every
wallet dir (40-hex address names) and processes all of its model dirs.

Usage: python3 lib/extract_report.py [dir ...]   # dirs optional; default = all
"""
import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# a wallet dir is named by the address itself
WALLET_RX = re.compile(r"^(0x)?[0-9a-fA-F]{40}$")

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

BAD_PREFIX = ('{', '[', '"', '$ ', '% ', '> ', '← ', '●', '•', '◈', '✓', '✗',
              '# ', '==', '<', '→', 'def ', 'import ', 'from ', 'print(',
              'Wrote ')
BAD_ANY = re.compile(
    r"import |def \w|print\(|curl |urllib|json\.|Traceback|Error|http|"
    r"\.py\b|python3|bash:|node:|exit code|API limit|timeout|</?\w+>", re.I)

STRAT_HINT = re.compile(
    r"strateg|grid|dca|scalp|martingale|trend|mean.reversion|arb|long|short|"
    r"entry|exit|hedge|pattern|rules|leverage|bias|liquidation|pyramid", re.I)
CHATTER_START = re.compile(r"^(I |I'|Let me|Excellent|Sure|Okay|Great)", re.I)
ANCHOR = re.compile(r"^(#{1,4} |\*\*|- |\* |\d+\. )|:$")
LEGACY_WALLET_HDR = re.compile(r"^# (Strategy description for this wallet|source:)")


def prose_line(ln: str) -> bool:
    s = ln.strip()
    if not s:
        return True
    if s.startswith(BAD_PREFIX) or "===" in ln:
        return False
    if BAD_ANY.search(ln):
        return False
    punct = sum(ln.count(c) for c in "{}[]\"")
    return not (punct >= 3 and punct > len(ln) * 0.10)


def final_prose(text: str, max_lines: int = 600) -> str:
    """Collect the trailing prose block of a transcript (the final answer)."""
    lines = [ANSI.sub("", ln).rstrip() for ln in text.splitlines()]
    out, started = [], False
    for ln in reversed(lines):
        if not started and not ln.strip():
            continue
        if prose_line(ln):
            out.append(ln)
            started = True
            if len(out) >= max_lines:
                break
        elif started:
            break
    out.reverse()
    while out and out[0].strip() in ("", "---"):
        out.pop(0)
    return "\n".join(out).strip()

def anchor_trim(block: str) -> str:
    """Drop leading tool-output fragments: keep from the oldest line that
    starts the answer (heading / bullet / numbered item / bold / lead-in ':')."""
    lines = block.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() and ANCHOR.search(ln):
            return "\n".join(lines[i:]).strip()
    return block


def manifest_statuses() -> dict:
    """label -> run status, merged from every wallet's manifest.tsv."""
    out = {}
    for mf in sorted(ROOT.glob("*/manifest.tsv")):
        rows = [ln.split("\t") for ln in mf.read_text(errors="replace").splitlines()
                if ln.strip()]
        for r in rows[1:]:
            if len(r) >= 10:
                out[r[9]] = r[0]
    return out


def deep_search(text: str) -> str:
    """Largest prose block anywhere in a partial transcript."""
    lines = [ANSI.sub("", ln).rstrip() for ln in text.splitlines()]
    best, cur = "", []
    for ln in lines + [""]:
        if ln and prose_line(ln):
            cur.append(ln)
        else:
            if len(cur) > len(best.splitlines()):
                best = "\n".join(cur)
            cur = []
    return best.strip()


def report_path(d: pathlib.Path) -> pathlib.Path:
    return d / "strategy_report.md"


def migrate(dirs, statuses) -> None:
    skip_reason = {"SKIPPED_NOT_FREE": "was skipped (model not free / probe failed)",
                   "TIMEOUT": "timed out before finishing",
                   "FAILED": "failed"}

    for d in dirs:
        rp = report_path(d)
        out_txt = d / "output.txt"
        wallet = d / "wallet.txt"
        status = statuses.get(d.name, "")
        work_mds = sorted((d / "work").glob("*.md"),
                          key=lambda p: p.stat().st_size, reverse=True)

        # 1. agent-written report wins; MOVE it here (delete original)
        moved = False
        if work_mds:
            if not rp.exists():
                work_mds[0].rename(rp)
                moved = True
            for extra in work_mds[1:]:
                if extra.read_text(errors="replace").strip() == rp.read_text(errors="replace").strip():
                    extra.unlink()
            if moved:
                print(f"MOVE   {d.name}: work/{work_mds[0].name} -> strategy_report.md")

        # 2. migrate legacy wallet.txt
        if wallet.exists() and not rp.exists():
            body = LEGACY_WALLET_HDR.sub("", wallet.read_text(errors="replace")).strip()
            wallet.unlink()
        else:
            if wallet.exists():
                print(f"DEL    {d.name}/wallet.txt (strategy_report.md already exists)")
                wallet.unlink()
            body = ""

        # 3. extract from output.txt when we still have nothing
        if not body and out_txt.is_file():
            text = out_txt.read_text(errors="replace")
            body = final_prose(text)
            if status in skip_reason:
                alt = deep_search(text)
                if len(alt) > 400 and len(alt.splitlines()) > max(3, len(body.splitlines()) * 2):
                    body = alt

        if body:
            body = anchor_trim(body)

        if status in skip_reason and (not body or len(body.splitlines()) < 3
                                      or not ANCHOR.search(body)):
            body = (f"NO STRATEGY — run {skip_reason[status]} "
                    f"({status}); no answer was produced.")
        elif not body:
            body = ("NO STRATEGY — no answer was produced "
                    "(no output.txt / empty run).")
        elif (len(body.splitlines()) < 4
              and (CHATTER_START.match(body) or not STRAT_HINT.search(body))):
            body = ("NO STRATEGY — run completed but the model never wrote a "
                    "strategy description (only tool chatter); see output.txt.")

        if not rp.exists():
            rp.write_text(f"# Strategy description for this wallet — {d.name}\n\n{body}\n")
            tag = "OK  " if not body.startswith("NO STRATEGY") else "FLAG"
            print(f"{tag}   {d.name}: strategy_report.md ({len(body.splitlines())} ln)")
        elif not moved:
            print(f"KEEP   {d.name}: strategy_report.md already present")

        # cleanup: empty work/ dirs left behind after the move
        work = d / "work"
        if work.is_dir() and not any(work.iterdir()):
            work.rmdir()

        # cleanup: probe.txt is a transient -- verdict lives in meta.json,
        # informative text is preserved in output.txt (Dedup #4)
        probe_file = d / "probe.txt"
        if probe_file.exists():
            probe_file.unlink()
            print(f"DEL    {d.name}/probe.txt (redundant: meta.json + output.txt)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dirs", nargs="*",
                    help="run dirs like <wallet>/<label> (default: every wallet dir)")
    a = ap.parse_args()

    if a.dirs:
        dirs = []
        for x in a.dirs:
            p = pathlib.Path(x)
            dirs.append(p if p.is_absolute() else ROOT / x)
    else:
        dirs = []
        for wallet in sorted(p for p in ROOT.iterdir()
                             if p.is_dir() and WALLET_RX.match(p.name)):
            for d in sorted(wallet.iterdir()):
                if d.is_dir() and ((d / "output.txt").is_file()
                                   or (d / "work").is_dir()
                                   or (d / "wallet.txt").is_file()
                                   or (d / "strategy_report.md").is_file()):
                    dirs.append(d)
    dirs = [d for d in dirs if (d / "meta.json").is_file()
            or d.name.startswith("smoke-")]
    migrate(dirs, manifest_statuses())


if __name__ == "__main__":
    main()