# agents.md — Hyperliquid strategy-sweep workspace

Everything needed to continue this work: what this is, how it was built, what
each file is, and how to rerun/extend it. Work dir:
`/home/paf/Documents/code/misc/hyperliquid-strategy-sweeps`.

Layout principle: **one folder per wallet, model folders inside it**
(`<wallet-address>/<model-label>/...`) — built for repeating the same sweep on
other wallets later (see §3b).

## 1. Mission

Compare how many free-tier coding CLIs/agents can derive a trader's strategy
from on-chain data. Wallets studied so far (one folder each):

```
0x0bb81e516c88881c54529e1790470cb5e9f8740d   (HYPE-PERP trader on hyperx.trade/Hyperliquid)
```

Prompt given to every model for this wallet (see
`0x0bb8…740d/prompt.txt`; each wallet has its own):

> derive the trading strategy or strategies used by
> https://hyperx.trade/hyperliquid/trader?address=0x0bb8...740d

Three CLIs are driven, each with several free models (`models.tsv`):

| tool | notes |
|---|---|
| `cline` | `--thinking <variant>` for reasoning effort |
| `kilo` | `--variant <v>`; model ids like `kilo/stepfun/step-3.7-flash:free` |
| `opencode` | model ids like `opencode/muse-spark-1.3-contributor-free` |

The known answer (consensus of the best runs): **long-only HYPE-PERP grid /
martingale DCA bot** — taker buy to open, maker limit adds ~-1% lower with
~0.5x→3.5x size scaling (up to ~12 levels), single reduce-only maker TP sell at
**avgEntry +0.84%**, ~1346 flat-to-flat cycles, +$5.4k closedPnl / -$97 funding,
no shorts, no stops, 10x cross setting (low realized). See
`0x0bb8…740d/oc-muse-spark-1.3/strategy_report.md` for the richest derivation.

## 2. Directory map

```text
run-models.sh          sweep driver — takes --wallet <address> (see §3)
models.tsv             30 rows: tool | model | label | variant | extra-args (shared)
discovery.tsv          --check-new verdicts for ids not in models.tsv: never
                       re-probe anything already judged here
lib/parse_free.py      parse `kilo models --verbose` / `opencode models --verbose`,
                       print free model ids (cline has no models listing — its
                       free list is fetched from its HTTP API inside run-models.sh)
lib/extract_report.py  build strategy_report.md in every run dir, ALL wallets (see §4)
<wallet-address>/      one dir per studied wallet:
  prompt.txt           the prompt every agent got for THIS wallet
  manifest.tsv         per-run result: status, tool, model, variant, probe,
                       gate, exit, duration_s, bytes, label
  sweep.log            console log of the last sweep for this wallet
  smoke-cline-solar-pro4/   one-model smoke test dir (same layout as model dirs)
  <label>/             one dir per model (label = 4th column of models.tsv):
    output.txt         full ANSI transcript (tool chatter first, FINAL ANSWER at tail)
    strategy_report.md THE deliverable: only the strategy description (see §4)
    meta.json          run record: wallet, status, exit, duration, bytes (one source)
    work/              (legacy, cline runs only) agent scratch during the run;
                       reports are moved out and the whole work/ dir is
                       removed post-sweep (see §6) -- absent on every dir now
```

Wallet dir names are the raw address (`0x…40hex`); `extract_report.py` finds
wallets by that pattern. Labels prefixed `unverified-` = model never proven
free on this account before the run; the run itself proved it (4 turned out
NOT free, see §5).

**Dedup principle ("one fact, one file"):** every fact lives in exactly one
place. meta.json owns the run record (status/exit/duration/bytes — the bare
`exit` files were removed as duplicates); `strategy_report.md` is the ONE
strategy answer per dir — no wallet.txt, no duplicate report inside work/
(both were removed as duplicates). Derived views (manifest.tsv) are
aggregations, not copies. Before adding any new file, check it isn't already
recorded elsewhere.

## 3. Running a sweep

```bash
cd /home/paf/Documents/code/misc/hyperliquid-strategy-sweeps
W=0x0bb81e516c88881c54529e1790470cb5e9f8740d
./run-models.sh --wallet $W --jobs 6 --timeout 1500 --resume                    # normal sweep
./run-models.sh --wallet $W --jobs 6 --timeout 1500 --resume --check-new        # + discover new free models first
./run-models.sh --wallet $W --jobs 8 --timeout 1500 --resume --only kilo        # one tool
./run-models.sh --wallet $W --jobs 8 --timeout 1500 --resume --only muse-spark-1.3 --force  # one model
```

`--wallet` is REQUIRED: runs land in `<wallet>/<label>/`, results in
`<wallet>/manifest.tsv`. The prompt defaults to `<wallet>/prompt.txt`
(create it first; `--prompt-file` overrides).

**`--check-new` (new-model discovery):** pulls each tool's current free list
(cline API / `kilo models` / `opencode models`), diffs it against `models.tsv`
and `discovery.tsv`, and PROBES every unknown id with the tiny plan-agent
prompt. "100% sure free" = listed free NOW **and** probe returns OK. Verified
ids are appended to `models.tsv` (auto label `new-<tool>-<model>`) and run
against the wallet prompt in the same sweep; rejected ids are recorded in
`discovery.tsv` (tool | model | verdict | date | note) and never re-probed.
Skipped entirely in `--dry-run`.

- `--jobs N` parallel agents; `--timeout S` per-run kill (1500 s was used);
- `--resume` skips models whose run already wrote output (restart-safe);
- `--force` rerun even if a result exists;
- `--only X` filters on label substring or tool name.
- **Rating gate:** models with at least one negative rating (−1) in the rating
  app's DB are NEVER sent prompts — not the run prompt, not even the tiny
  free-check probe. The driver reads the blocklist from the app's Postgres
  once at sweep start (one `docker compose` psql call; fail-open with a
  warning if the app/db is down). Blocked runs get status
  `SKIPPED_NEGATIVE_RATING` in
  meta.json (or keep their previous record if one exists); discovery also
  refuses to probe blocked ids. Lift a block by removing the −1 in the app,
  then rerun (with `--force` for that model if a result exists).
- **Critical bug fixed during sweep #1:** agents MUST be launched with
  stdin=/dev/null (`timeout ... < /dev/null`); otherwise they inherit the
  driver loop's stdin and hang (run-models.sh line ~281).
- Wall time: full 30-model sweep ≈ 1.5–2 h at `--jobs 6`.

## 3b. Adding a new wallet

```bash
cd /home/paf/Documents/code/misc/hyperliquid-strategy-sweeps
W=0x<NEW-40HEX-ADDRESS>
mkdir -p "$W"
cp 0x0bb81e516c88881c54529e1790470cb5e9f8740d/prompt.txt "$W/prompt.txt"
sed -i "s/0x0bb8[^? ]*/$W/g" "$W/prompt.txt"       # point it at the new address
./run-models.sh --wallet $W --jobs 6 --timeout 1500 2>&1 | tee "$W/sweep.log"
python3 lib/extract_report.py                       # builds strategy_report.md everywhere
```

Notes:
- `models.tsv` and `lib/` are shared across wallets — no changes needed.
- Per-wallet state (prompt, manifest, transcripts, strategy reports) lives
  entirely inside `$W/`; wallets are fully independent.
- Free-tier budgets are per account/day, shared across wallets — expect daily
  caps (esp. cline) to hit sooner when sweeping two wallets the same day.
- After the sweep, sanity-check `$W/manifest.tsv`, spot-check a few
  `strategy_report.md` files against §7's checklist pattern (numbers will of
  course differ per wallet; the fingerprint structure is what to validate).

Adding models: append to `models.tsv` (find free ids with
`kilo models --verbose | python3 lib/parse_free.py kilo`, same for opencode).

## 4. After a sweep: build strategy_report.md (the deliverable)

Every model dir gets **one** `strategy_report.md` containing only the strategy
description that model produced for the wallet — no code, no raw API dumps, no
chatter. Build/refresh (idempotent):

```bash
python3 lib/extract_report.py            # all dirs; or pass specific dirs
```

How it decides what to keep (single deliverable, learned from sweep-#1 bugs):
0. **If the agent wrote its own report (`work/*.md`, cline runs do), that
   content is MOVED to `strategy_report.md`** (original deleted — moving, not
   copying, keeps one fact in one file).
1. Legacy `wallet.txt` from older sweeps is migrated into it and deleted.
2. Otherwise the trailing prose block of `output.txt` is extracted (models end
   with their final answer; everything earlier is tool chatter), anchored at
   the first heading/bullet/bold lead-in line.
   HARNESS DIFFERENCE: kilo/opencode answers live in output.txt (their final
   message). cline agents instead write deliverables straight to disk via file
   tools — output.txt shows only TRUNCATED tool-call previews, so for cline
   runs the report file IS the original record (output.txt just proves the
   write happened). deepseek-v4.1-flash's report is chunk 1 of ~3: the daily
   free limit killed it right after the first chunk (mtime 09:23 = the write,
   limit error right after in the transcript).
3. Runs with no real answer get flagged INSTEAD:
   `NO STRATEGY — run was skipped/failed/timed out ...` (reason from
   `manifest.tsv` status).
4. A dir has ONLY `strategy_report.md` — the script deletes any `wallet.txt`
   or leftover `work/*.md` duplicates it finds, and removes all `work/`
  contents (agent scratch) plus any leftover wallet.txt / probe.txt.

Current state: 31 runs = 31 `strategy_report.md` (22 with a strategy
description + 9 `NO STRATEGY` flags), 0 `wallet.txt`, 0 `work/` dirs.
`output.txt` is the evidence trail — don't delete it; `strategy_report.md` is
self-contained if you only want the answers.

## 5. Sweep #1 results (2026-09-20) — what happened, per status

`manifest.tsv` summary: **19 DONE / 4 FAILED / 3 TIMEOUT / 4 SKIPPED_NOT_FREE**.

- **Displayed status vs raw status.** A run's raw `status` (DONE/FAILED/TIMEOUT/
  SKIPPED_NOT_FREE) is stored in `meta.json`. The UI shows `display_status`,
  which is `DONE` whenever the run produced a real answer
  (`has_real_report`, set by `importer._is_real_report` from
  `strategy_report.md`) — even if the raw status is TIMEOUT or FAILED. So a
  run that was killed by the 1500s wall-clock limit *after* writing a complete
  report shows as DONE, not TIMEOUT. `has_report` in the API is the same
  boolean; the wallets view's "done" count sums `has_real_report`, not
  `status='DONE'`.

- DONE (16 verified + 3 unverified-*): kilo strong (laguna-s-2.1,
  step-3.7-flash, nemotron-3-ultra, ling-3.0-flash-vl, dots-3-note-preview),
  opencode strong (muse-spark-1.2/1.3, mimo-v2.5, big-pickle).
- SKIPPED_NOT_FREE (probe correctly gated them): kilo-deepseek-v4-flash-0731
  (retired), oc-jev-1.13, unverified-kilo-{inkling-small, qwen3.8-27b}.
- TIMEOUT at 1500 s (partial output in output.txt; rerunnable with `--force`):
  cline-glm-5.3-flash + cline-laguna-s-2.1 (both still wrote full strategy
  reports, now at strategy_report.md), kilo-laguna-xs-2.1 (no answer).

  Note: cline-glm-5.3-flash and cline-laguna-s-2.1 were killed by the
  wall-clock limit *after* their agents had already written and submitted
  complete reports (see output.txt tails — `submit_and_exit` recorded). Their
  raw status is TIMEOUT (exit 124) but the UI shows DONE via `display_status`,
  because `has_real_report` is true.
- FAILED, causes (none rerunnable at time of failure):
  - cline-deepseek-v4.1-flash — **daily free limit reached**, "Try again in 6h".
    Wrote its strategy report first; rerun later with `--force`.
  - cline-solar-pro4 — Hyperliquid API rate limiting / idle timeout; never
    reached the analysis stage.
  - unverified-kilo-nemotron-3.5-lightning — upstream idle timeout.
  - unverified-kilo-nex-n2.5-pro — **context overflow**: ingested raw fills
    until 280k > 262k token limit.

Lessons learned: cline's free tier is the most rate-limited (daily caps);
`kilo --variant thinking` tends to burn context on raw data dumps (biggest
transcripts); opencode is fast/cheap but its smaller models answer from page
metadata only (oc-lfm-2.5, oc-nemotron-3-ultra never pulled real data).

## 6. Housekeeping / TODO

- Deleted after the sweep: `*/work/data/` (6.9 MB raw API dumps) and
  `*/work/scripts/`, plus remaining scratch (glm's 12 top-level *.json, muse's
  fills.json + replicate_strategy.py, solar-pro4's *.py) — not needed once
  strategy_report.md exists. All `work/` dirs are now gone.
- Dedup #1 (wallet.txt vs work/*.md): superseded — see Dedup #3.
- Dedup #2 (exit file vs meta.json): the bare `<dir>/exit` files duplicated
  meta.json's "exit" field for all 30 runs. Deleted the files and removed all
  5 `echo ... > "$dir/exit"` write sites from run-models.sh; exit code lives
  ONLY in meta.json now. (Verified all 30 matched before deleting; --resume
  and manifest.tsv read meta.json only, so nothing else was affected.)
- Dedup #3 (one deliverable name): wallet.txt and work/*.md replaced by a
  single `strategy_report.md` per dir via `lib/extract_report.py`
  (extract_wallet.py deleted). Driver layout unchanged for future runs.
- Dedup #4 (probe.txt vs meta.json): all 30 probe.txt files removed. The
  verdict is meta.json's "probe" field; the only informative probe text
  (the SKIPPED_NOT_FREE paywall output) is byte-identical to output.txt,
  which the driver copies (verified 30/30 before deleting). run-models.sh
  now keeps probe output in a temp file, so future sweeps create none.
- Kept overlaps (intentional): manifest.tsv is a derived aggregation of all
  meta.json (not a copy); output.txt doubles as the transcript of
  SKIPPED_NOT_FREE runs, whose only activity was the failed probe.
- Dedup #5 (work/ agent scratch vs strategy_report.md): cline runs leave a
  work/ dir with raw API dumps (fills_page_*.json) and analysis scripts.
  extract_report.py now deletes ALL work/ contents after moving the report
  (Dedup #5). Future sweeps: work/ is gone from every dir.
- After any rerun or model-list change: rerun the sweep, then
  `python3 lib/extract_report.py`, then update §5/§7 numbers here.

## 7. Quick reference: consensus strategy (validate future runs against this)

Any good answer should reconstruct roughly this (muse-1.3 / laguna-s /
step-3.7 / big-pickle all agree):

- Universe: HYPE-PERP only, long-only, no spot, no shorts, ~11 months of data
  (2025-10 → 2026-09), price range $23.32–$94.15.
- Cycle: taker open (~2.8–3.4% of equity notional) → maker adds ~-1% lower
  (0.5x/1x/1.8x/3.6x ladder, up to 9–11 adds) → single full reduce-only maker
  sell at avgEntry +0.84% → repeat. ~5 cycles/day, ~1346 total.
- Result: +$5,458 closedPnl, $268 fees, −$97 funding, 1440/1443 positive
  closes; survived the −36% Dec-2025 drawdown with a ~280 HYPE stack
  (~2–3x realized leverage on ~$3.5k).
- Failure mode to flag: no stop-loss; a >40–50% HYPE flush filling the whole
  ladder (~$40k) on ~$12k equity = liquidation risk.

## 8. Rating app (FastAPI + Postgres + React/TS, dockerized)

Review the sweep results in a browser: wallets → models → strategy report →
rate 👍/👎; models with the most positive ratings rank on top (summed across
all wallets — the runs table keys on (wallet, label) so future wallets just
work via `make import` or a restart).

- `docker-compose.yml`  db (postgres:16, init.sql schema) + backend (:8000)
  + frontend (nginx :8080, proxies /api → backend). Postgres data persists
  in the `pgdata` volume.
- `Makefile`            `make start|stop|logs|import|psql|clean`
- `app/backend/`        FastAPI (main.py: /api/wallets, /api/wallets/{a}/runs,
                        /api/runs/{id}, POST /api/runs/{id}/rating,
                        /api/leaderboard, POST /api/import), db.py (psycopg2
                        pool), importer.py (scans all wallet dirs; idempotent),
                        init.sql (wallets, runs, ratings tables)
- `app/frontend/`       React 18 + TypeScript + Vite (job-market standard),
                        three views in App.tsx, API client api.ts
- Import runs automatically on backend startup and via `make import`.
  Ratings live in Postgres (not files); one rating per run, values -1/+1.


