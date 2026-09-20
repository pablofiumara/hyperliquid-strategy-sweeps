"""Scan DATA_DIR for wallet dirs (0x…40hex) and their model runs, upsert to DB.

Idempotent: safe to run on every startup and via POST /api/import.
"""
import json
import os
import pathlib
import re

import db

DATA_DIR = pathlib.Path(os.environ.get("DATA_DIR", "/data"))
WALLET_RX = re.compile(r"^(0x)?[0-9a-fA-F]{40}$")


def import_all() -> dict:
    wallets = runs = 0
    for wdir in sorted(DATA_DIR.iterdir()):
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
                                  probe, duration_s, bytes, report_path)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (wallet, label) DO UPDATE SET
                    tool=EXCLUDED.tool, model=EXCLUDED.model,
                    variant=EXCLUDED.variant, status=EXCLUDED.status,
                    probe=EXCLUDED.probe, duration_s=EXCLUDED.duration_s,
                    bytes=EXCLUDED.bytes, report_path=EXCLUDED.report_path
                """,
                (
                    wdir.name, m.get("label", mdir.name), m.get("tool"),
                    m.get("model"), m.get("variant"), m.get("status"),
                    m.get("probe"), m.get("duration_s"), m.get("bytes"),
                    str(report) if report.is_file() else None,
                ),
            )
            runs += 1
    return {"wallets": wallets, "runs": runs}
