"""Remove agent scratch (raw API dumps, analysis scripts, duplicate files).

After a model produces its answer the only thing worth keeping is
`strategy_report.md` (the deliverable) and `output.txt` (the evidence trail).
Everything else in a run dir is disposable:

  work/            raw API dumps (fills_page_*.json, candles_1d.json, ...),
                   analysis scripts, intermediate JSON -- several MB per run.
  wallet.txt       legacy duplicate of strategy_report.md (pre-sweep #1).
  probe.txt        transient free-gate probe; verdict lives in meta.json.

Safe by construction: `work/` is only removed when `strategy_report.md`
already exists, so an in-progress run (no report yet) is never touched.
Idempotent -- safe to call repeatedly.
"""
import json
import pathlib
import re
import shutil

import db

DATA_DIR = pathlib.Path(__import__("os").environ.get("DATA_DIR", "/data"))
WALLETS_DIR = pathlib.Path(__import__("os").environ.get("WALLETS_DIR", str(DATA_DIR / "wallets")))
WALLET_RX = re.compile(r"^(0x)?[0-9a-fA-F]{40}$")

DISPOSABLE = ("wallet.txt", "probe.txt")


def _clean_run_dir(mdir: pathlib.Path) -> dict:
    """Remove scratch from one model dir. Returns what was removed."""
    removed: list[str] = []
    report = mdir / "strategy_report.md"

    # Only touch dirs whose answer is already extracted -- never delete
    # scratch from a run that hasn't produced a report yet.
    if not report.is_file():
        return {"dir": mdir.name, "removed": removed, "skipped": "no report"}

    for name in DISPOSABLE:
        p = mdir / name
        if p.is_file():
            p.unlink()
            removed.append(name)

    work = mdir / "work"
    if work.is_dir():
        for item in sorted(work.iterdir()):
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
            removed.append(f"work/{item.name}")
        if not any(work.iterdir()):
            work.rmdir()

    return {"dir": mdir.name, "removed": removed, "skipped": ""}


def cleanup_all() -> dict:
    """Walk every wallet + model dir and purge disposable scratch.

    Returns a summary plus a per-dir list of what was removed.
    """
    dirs_touched = 0
    bytes_freed = 0
    details: list[dict] = []
    for wdir in sorted(WALLETS_DIR.iterdir()):
        if not (wdir.is_dir() and WALLET_RX.match(wdir.name)):
            continue
        for mdir in sorted(wdir.iterdir()):
            if not mdir.is_dir():
                continue
            if not ((mdir / "meta.json").is_file() or mdir.name.startswith("smoke-")):
                continue
            before = sum(f.stat().st_size for f in mdir.rglob("*") if f.is_file())
            res = _clean_run_dir(mdir)
            after = sum(f.stat().st_size for f in mdir.rglob("*") if f.is_file())
            freed = before - after
            bytes_freed += freed
            if res["removed"]:
                dirs_touched += 1
                details.append({**res, "bytes_freed": freed})
    return {
        "wallets_scanned": sum(
            1 for w in WALLETS_DIR.iterdir()
            if w.is_dir() and WALLET_RX.match(w.name)
        ),
        "dirs_cleaned": dirs_touched,
        "bytes_freed": bytes_freed,
        "details": details,
    }


def cleanup_wallet(address: str) -> dict:
    """Cleanup for a single wallet dir (used by the per-wallet endpoint)."""
    wdir = WALLETS_DIR / address
    if not wdir.is_dir():
        return {"wallet": address, "error": "not found"}
    dirs_touched = 0
    bytes_freed = 0
    details: list[dict] = []
    for mdir in sorted(wdir.iterdir()):
        if not mdir.is_dir():
            continue
        before = sum(f.stat().st_size for f in mdir.rglob("*") if f.is_file())
        res = _clean_run_dir(mdir)
        after = sum(f.stat().st_size for f in mdir.rglob("*") if f.is_file())
        freed = before - after
        bytes_freed += freed
        if res["removed"]:
            dirs_touched += 1
            details.append({**res, "bytes_freed": freed})
    return {
        "wallet": address,
        "dirs_cleaned": dirs_touched,
        "bytes_freed": bytes_freed,
        "details": details,
    }


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else None
    res = cleanup_wallet(target) if target else cleanup_all()
    print(json.dumps(res, indent=2))