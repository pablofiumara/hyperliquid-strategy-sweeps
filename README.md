# Hyperliquid Strategy Sweeps

Run free LLM CLI agents (**cline**, **kilo**, **opencode**) against onchain
wallets to reverse-engineer their trading strategy, then review and rate the
answers in a small web app.

**Status badge of the first sweep:** 30 models × wallet `0x0bb8…740d` →
19 completed, 22 strategy reports usable, 9 flagged `NO STRATEGY`.

## The studied wallet

`0x0bb81e516c88881c54529e1790470cb5e9f8740d` (hyperx.trade / Hyperliquid).
Consensus answer across the best models: a **long-only, single-coin
HYPE-PERP grid/martingale DCA maker** — base entry ~3% of equity, adds at
~-1% steps (0.5x→3.5x scaling), full-stack take-profit at **+0.84%**,
~1,346 flat-to-flat cycles, +$5,458 closed PnL over ~11 months. Full
reference: [agents.md §7](agents.md).

## Repo layout

```text
run-models.sh          sweep driver (--wallet, --probe-jobs, --resume, --dry-run)
discovery.tsv          append-only history of free-check probe verdicts
models.tsv             model registry: tool | model | label | variant | extra-args
lib/parse_free.py      parse kilo/opencode free-model listings
lib/extract_report.py  build strategy_report.md in every run dir (all wallets)
agents.md              full ops manual: procedures, lessons, dedup rules
<0x-wallet-address>/   one dir per wallet
  prompt.txt           the exact prompt given to every agent
  manifest.tsv         per-run results table
  <model-label>/       output.txt (full transcript), strategy_report.md,
                       meta.json (run record)
app/                   rating app (FastAPI + Postgres + React/TypeScript)
docker-compose.yml     db + backend + frontend
Makefile               make start | stop | logs | import | psql | clean
```

## How it works

1. **Verify free models** — every sweep, before anything is prompted: the
   driver polls each tool's live free list and probes every listed model with a
   tiny request. Only models that come back `$0`-free reach the real prompt,
   and newly free ones are added to `models.tsv` automatically. Verdicts are
   never cached across sweeps (`--no-verify` / `--no-check-free` opt out).
2. **Run the prompt** — each agent gets `prompt.txt` for the wallet and must
   produce a strategy description. Runs are gated, logged, and resumable
   (`--resume`, `--jobs`, `--timeout`).
3. **Extract reports** — `python3 lib/extract_report.py` distills every run
   into a single `strategy_report.md` (agent-written reports are moved in;
   others are extracted from the transcript tail; no-answer runs are
   flagged).
4. **Rate & rank** — open the app, read reports, 👍/👎 them; a model's score
   sums across all wallets, and models are ranked by it.

## Rating app

```bash
make start        # builds + starts db, backend (:8000), frontend (:8080)
# open http://localhost:8080
make import       # re-scan wallet dirs into Postgres (also runs on startup)
make clean        # stop and drop the database volume
```

Screens: wallets → models (sorted by score) → strategy report → rating.
Data model: `wallets`, `runs (wallet,label unique)`, `ratings (-1|+1)`.
A model with ≥1 negative rating is excluded from future sweeps by
`run-models.sh`'s rating gate (no prompts, not even free-check probes).

## Notes & caveats

- Free tiers are rate-limited: daily caps (cline), idle timeouts, and
  context limits caused the 11 non-DONE runs in sweep #1 — rerunnable with
  `--force` after limits reset.
- Everything here was produced by LLM agents reading public Hyperliquid
  API data; descriptions are hypotheses, not financial advice.
- See [agents.md](agents.md) for the complete operating manual and the
  lessons learned (single-source-of-truth rules, probe gating, dedups).
