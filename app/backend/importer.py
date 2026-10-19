"""Scan DATA_DIR for wallet dirs (0x…40hex) and their model runs, upsert to DB.

Idempotent: safe to run on every startup and via POST /api/import.
"""
import json
import os
import pathlib
import re

import db

DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", "/data"))
WALLETS_DIR = pathlib.Path(os.environ.get("WALLETS_DIR", str(DATA_DIR / "wallets")))
WALLET_RX = re.compile(r"^(0x)?[0-9a-fA-F]{40}$")

# model_id -> context window (tokens). One fact, one place: see
# ../lib/context_sizes.tsv. Unknown models get 0 (shown as "—" in the UI).
_CONTEXT: dict[str, int] = {}
# DATA_DIR is the repo root (/data at runtime), so the registry is at
# <DATA_DIR>/lib/context_sizes.tsv. Fall back to the module's own location so
# the same code works when run from a source checkout.
_reg = DATA_DIR / "lib" / "context_sizes.tsv"
if not _reg.is_file():
    _reg = pathlib.Path(__file__).resolve().parent.parent.parent / "lib" / "context_sizes.tsv"
for _line in _reg.read_text(errors="replace").splitlines():
    _line = _line.split("#", 1)[0].strip()
    if not _line or "\t" not in _line:
        continue
    _mid, _ctx = _line.split("\t", 1)
    try:
        _CONTEXT[_mid.strip()] = int(_ctx.strip())
    except ValueError:
        pass


def context_size(model: str | None) -> int:
    """Context window for a run's model; 0 if unknown."""
    if not model:
        return 0
    return _CONTEXT.get(model, 0)


def _is_real_report(p: pathlib.Path) -> bool:
    """True when strategy_report.md is an actual answer, not a flag/preview.

    DONE requires a real description: reject NO STRATEGY flags AND truncated
    harness previews (cline `submit_and_exit` records only ~100 chars ending
    in "..." when the agent never wrote work/*.md).
    """
    if not p.is_file():
        return False
    try:
        text = p.read_text(errors="replace")
    except OSError:
        return False
    head = text[:300]
    if head.startswith("NO STRATEGY") or "NO STRATEGY" in head:
        return False
    body = text.split("\n\n", 1)[-1].strip() if "\n\n" in text else text.strip()
    # truncated submit_and_exit preview, not a description
    if body.startswith("⎿ Submission recorded"):
        return False
    if body.endswith("...") and len(body) < 1000:
        return False
    if len(body) < 1000:
        return False
    return True


def import_all() -> dict:
    wallets = runs = 0
    for wdir in sorted(WALLETS_DIR.iterdir()):
        if not (wdir.is_dir() and WALLET_RX.match(wdir.name)):
            continue
        db.execute(
            "INSERT INTO wallets(address) VALUES (%s) ON CONFLICT DO NOTHING",
            (wdir.name,),
        )
        wallets += 1
        for mdir in sorted(wdir.iterdir()):
            meta = mdir / "meta.json"
            if not (mdir.is_dir() and meta.is_file()):
                continue
            try:
                m = json.loads(meta.read_text(errors="replace"))
            except json.JSONDecodeError:
                continue
            report = mdir / "strategy_report.md"
            db.execute(
                """
                INSERT INTO runs (wallet, label, tool, model, variant, status,
                                  probe, duration_s, bytes, report_path,
                                  context_size, has_real_report)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (wallet, label) DO UPDATE SET
                    tool=EXCLUDED.tool, model=EXCLUDED.model,
                    variant=EXCLUDED.variant, status=EXCLUDED.status,
                    probe=EXCLUDED.probe, duration_s=EXCLUDED.duration_s,
                    bytes=EXCLUDED.bytes, report_path=EXCLUDED.report_path,
                    context_size=EXCLUDED.context_size,
                    has_real_report=EXCLUDED.has_real_report
                """,
                (
                    wdir.name, m.get("label", mdir.name), m.get("tool"),
                    m.get("model"), m.get("variant"), m.get("status"),
                    m.get("probe"), m.get("duration_s"), m.get("bytes"),
                    str(report) if report.is_file() else None,
                    context_size(m.get("model")),
                    _is_real_report(report),
                ),
            )
            runs += 1
    return {"wallets": wallets, "runs": runs}
