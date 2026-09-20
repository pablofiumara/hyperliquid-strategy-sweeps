# Trading Strategy Derivation — Hyperliquid Trader 0x0bb8…740d

**Source data (all pulled live from `api.hyperliquid.xyz` /info on 2026-09-20):**
`clearinghouseState`, `openOrders`, `userFills` (2,000 most recent fills, the API maximum, covering 2026-05-22 → 2026-09-20), `userFunding` (485 records), `spotClearinghouseState`, `portfolio` (all-time weekly equity/PnL curve back to 2025-10-15). Fill-level history before 2026-05-22 is beyond the API's 2,000-fill window, so the pre-May period is characterized from the portfolio equity/PnL curve only.

---

## 1. Verdict

This account runs **one strategy**: a **long-only, single-asset (HYPE) grid / averaging-down scalper** — colloquially a "buy-the-dip ladder with a tight VWAP take-profit and Martingale sizing." It is almost certainly automated (24/7 operation, mechanical price/size geometry, ~4–7 cycles per day, uniform across all hours).

There is no evidence of shorting, other assets, stop-losses, or discretionary behavior anywhere in the data.

---

## 2. The strategy loop (reverse-engineered from fills + resting orders)

Each **cycle** (542 complete cycles observed in 122 days):

1. **Trigger — initial clip (always taker).** A market/IOC buy of a base clip (median 4.5 HYPE ≈ $400) fires when price has pulled back to roughly the level of the previous cycle's exit — measured displacement of the first buy vs. the previous cycle's final exit: median **+0.02%** (p10 −0.15%, p90 +0.22%). I.e., the bot re-arms each time price returns to the last take-profit level.
   - Evidence: 542/542 first entries were taker fills (0% maker).

2. **Take-profit — immediately placed (always maker).** A reduce-only limit sell for the whole clip is placed at **entry VWAP × 1.0084**.
   - Evidence: exit price vs. the *running* VWAP at exit time: median **+0.840%**, p10 **+0.839%** — an extremely tight distribution → a hard-coded +0.84% target, not discretionary.
   - Live confirmation right now: long 13.9 HYPE @ entry $92.1758 with a resting reduce-only ask at **$92.95 = 92.1758 × 1.00841**. ✓
   - 529 of 565 exits were a single fill; 559/565 exits (99%) were maker.

3. **Averaging-down ladder (always maker).** If price falls instead of recovering, the bot layers bids below:
   - consecutive add-on fill spacing: median **−1.02%** below the previous fill (min −4.6%);
   - add-on size scales up geometrically (Martingale): mean size ratio **×1.69**; the currently resting ladder shows a cleaner **×1.88 per rung**;
   - ladder depth reached in practice: median −3.1%, worst **−16%**;
   - 699/699 add-on fills were maker (100%).
4. **TP reprice.** After each add-on fills, the reduce-only ask is repriced to the **new blended VWAP × 1.0084** — so every averaged-down coin still exits at +0.84% over its average cost (verified: realized PnL / exit notional median **0.833%** ≈ target 0.84% less ~0.01% fees).
5. **Fill → sell whole position → repeat.** Median holding period per cycle: **~75 minutes**; mean 6.6 cycles/day; operating uniformly 24 h/day (flat hour-of-day histogram).

**Currently resting ladder (as of 2026-09-20, market ≈ $92.2):**

| Rung | Bid px | Size (HYPE) | Notional | Size ratio | Dist. below mkt |
|---|---|---|---|---|---|
| 1 | 88.454 | 11.71 | $1,036 | — | −4.0% |
| 2 | 86.572 | 21.96 | $1,901 | ×1.88 | −6.1% |
| 3 | 82.808 | 40.26 | $3,334 | ×1.83 | −10.2% |
| 4 | 79.044 | 75.03 | $5,931 | ×1.86 | −14.3% |
| 5 | 73.398 | 140.91 | $10,343 | ×1.88 | −20.4% |
| 6 | 67.752 | 265.35 | $17,978 | ×1.88 | −26.5% |
| **Σ** | | | **$40,522** | | |

Plus the reduce-only TP ask 13.9 HYPE @ $92.95.

---

## 3. Execution & cost profile (May 22 – Sep 20 window)

| Metric | Value |
|---|---|
| Instrument / direction | HYPE-PERP, long only (1,405 Open-Long fills, 595 Close-Long, zero shorts) |
| Complete cycles | 542 (≈ 4.4/day; days active: 6.6/day) |
| Win rate | **542/542 = 100%** — zero losing cycles, zero stop-outs |
| Closed PnL (window) | **+$3,209.60** (median $2.97/cycle, p90 $10.37, max $107.59) |
| Volume | $815,901 (≈ 6.6× account per month) |
| Fees | $168.45 → **2.06 bps** avg (discounted fee tier) |
| Funding | **−$96.95** net paid (485 hourly payments; long pays when HYPE perp funding is positive) |
| Position sizing | first clip median 4.5 HYPE; median cycle total 5.36 HYPE; p90 18 HYPE; **max 221.6 HYPE (~$14k)** in the 2026-05-22 flash-dip episode |
| Margin mode | cross, up to 10× allowed; typical deployed margin ≤ ~$130–1,500 |

## 4. Account-level economics

- Net deposits ≈ **$3,005** (account value $8,089 − all-time PnL $5,084).
- All-time PnL curve (weekly buckets): +$929 by Dec 2025 (first phase), +$1,825 by May 2026, **+$5,084 today** → ≈ **+169% on deposits in ~11 months**, with the current phase (~4 months) contributing +$3,259.
- The trader periodically withdraws everything (account value reads $0 during Jan 1–Feb 10 and May 6–13, 2026, with PnL flat) and re-deposits — profit harvesting, not liquidations (PnL never steps down).
- ~$3.9k of the $8.1k sits idle in the spot wallet as a reserve buffer; ~$4.2k is the perp margin backing the ladder (which, if fully filled at the current rungs, would need ~$4k margin at 10×).

## 5. The risk being taken (this is the crux)

The strategy is a **short-volatility / no-stop Martingale grid**. It converts a small edge (+0.84% per oscillation, harvested ~0.83% after costs) into steady income **by accepting unbounded tail risk on the way down**:

- No stop-loss ever appears in 2,000 fills — every dip is averaged, never cut. The 100% win rate is definitional, not skill: a cycle only "closes" when price recovers to VWAP×1.0084.
- Resting bids of **$40.5k notional ≈ 9.6× the $4.2k perp account** sit up to −26.5% below market. A fast HYPE drawdown through the full ladder would consume the entire account (cross-margined; liquidation before the bottom rungs fill). The May 22 episode (−16% ladder, 221 HYPE, recovered in ~26 h) shows the bot's sizing assumption: dips revert within hours.
- Long-bias funding drag (−$97 in 4 months) and gap/liquidity risk on HYPE (a low-float, high-beta altcoin) are the recurring bleed; a single sustained crash > ~27% with no bounce is the kill-scenario.

## 6. Classification

| Taxonomy | Fit |
|---|---|
| Style | High-frequency market-making-like grid scalping (passive exits, aggressive entries) |
| Family | Averaging-down DCA grid + Martingale sizing, fixed take-profit |
| Edge harvested | Mean reversion of HYPE micro-dips (~0.84% amplitude) at ~4–7 occurrences/day |
| Direction/asset | Long-only, HYPE-PERP exclusively |
| Risk profile | Positive-skew daily PnL, hidden left tail; leveraged ladder, no stop |
| Automation | Fully mechanical (24/7 hour histogram, deterministic +0.84% TP, geometric ladder) |

## 7. Reproducibility

- `analyze1.py` — fill statistics, cycle reconstruction (validated field-by-field against each fill's `startPosition`), per-cycle detail.
- `analyze2.py` — TP geometry, ladder spacing/sizing, funding, equity curve.
- `analyze3.py` — maker/taker by ladder position, funding net, live order ladder, all-time curves.
- `analyze4.py` — TP vs running VWAP, cycle re-arm displacement, exit/PnL ratios.
- Raw API payloads: `userFills.json`, `userFunding.json`, `openOrders.json`, `clearinghouse.json`, `portfolio.json`, `spotClearinghouseState.json`.

