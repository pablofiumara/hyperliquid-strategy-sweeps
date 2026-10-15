# Strategy description for this wallet — oc-big-pickle

## Data & method

Hyperliquid `info` API on `0xe755…e578`: 2,000 fills (the `userFills` response cap) spanning **2026-06-02 → 2026-09-26**, 11 perps, $116,033 notional; plus `userFunding` (back to 2026-03-13) and `portfolio` equity curve (2026-01-28 → now: $0 → $2,194, lifetime volume $141,512).

One API caveat that matters: the `dir` field always reads `Open Long`/`Close Long`, but the account **crosses through zero** (133 sign flips on HYPE alone) — position state must be reconstructed from `side`, not `dir`.

## The strategy: two modules

### Module A — "laddered long scalper" (the engine; 10 alt perps, live since 08-25)

Long-only. 1,483 buys / 517 sells → **329 completed round-trips, 4.2/day, ~1h median hold**. Mechanics per trade:

1. Place 2–8 **descending limit buys** below market. Rung spacing 4–123 bps, rung size grows **1.05–1.21× per rung** (mild pyramid).
2. Let them fill (median build time 0.2–2.0h, ladder depth median 27–500 bps, p95 to 1,437 bps).
3. Sell **100% of the accumulated size in a single resting limit at exactly VWAEP × (1+TP)**.

TP is a fixed per-coin constant, and realized return matches it to an **IQR of 0.1 bp** — proof the exit is a *placed limit*, not a market order:

| coin | TP bps | ladder depth (med) | size growth/rung | med hold | cycles | rung-0 $ |
|---|---|---|---|---|---|---|
| ZEC | 60 | 62 | 1.00 | 0.2h | 39 | 27 |
| XMR | 70 | 27 | 1.05 | 0.5h | 66 | 29 |
| INJ | 150 | 115 | 1.07 | 1.0h | 34 | 33 |
| ZRO | 150 | 202 | 1.20 | 0.8h | 49 | 25 |
| JUP | 155 | 500 | 1.11 | 1.0h | 18 | 19 |
| XLM | 190 | 171 | 1.08 | 20h | 5 | 34 |
| NEAR | 200 | 112 | 1.07 | 1.4h | 66 | 53 |
| ONDO | 210 | 165 | 1.21 | 1.7h | 36 | 14 |
| UNI | 210 | 135 | 1.08 | 2.6h | 15 | 22 |

**Result: 328 of 329 cycles profitable.** Median cycle +$1.58, 97.9% win rate. The single loser: ZEC, −$2.21, 6 rungs, 231 bps deep, 24-min hold. Sizing is fixed in *base units* ($14–53), not equity-scaled.

### Module B — "HYPE persistent long" (06-02 → 09-24, 114 days)

259 adds ($17,803, median $60) / 114 trims ($17,881, median $92). Position oscillates around a small core: median notional **$21**, max $662, with brief excursions to −$92 (it does cross short). 98% of trims profitable, median +$1.6, max +$23.7 → **+$340.8**. Median 85 min between actions but gaps up to 22 days. Same "harvest above blended cost" discipline, just never fully de-risked.

### Universe selection is momentum, not mean-reversion

New coins are entered at the **median 96th percentile of their prior-30-day range** (+13.5% median 7-day prior return). It buys breakout leaders and grids the post-breakout chop.

| UNI | ZEC | NEAR | JUP | XMR | HYPE | ONDO | INJ | ZRO | XLM | BTC | ETH |
|---|---|---|---|---|---|---|---|---|---|---|---|
| +218% | +184% | +100% | +98% | +57% | +50% | +48% | +44% | +43% | +8% | +14% | +34% |

Alt daily vol 4.0–7.2% — that's what makes a 0.6–2.1% intraday target reliably reachable.

## Economics

| | |
|---|---|
| Gross trading P&L (116d) | +$868.72 |
| Fees (74% maker @1.44bp, 26% taker @4.32bp) | −$24.40 |
| Funding | −$20.91 |
| **Net** | **+$823.41 on $116,033 vol = 71 bps of volume** |
| Last 30d | $87,248 vol → **+$590 net (67.6 bps)**, ≈$19.7/day on $2.1k equity ≈ **0.94%/day (~28%/mo)** |
| Peak position notional | $67–662/coin = **3–30% of equity**, ~50–70% gross |
| Max equity drawdown (sampled curve) | **−9.1%** ($890 → $809, late July) |

## Read on it

The 99.7% cycle win rate is a **grid-mechanical artifact** — a limit resting at a fixed spread above a computed cost basis fills almost mechanically in a 4–7% daily-vol regime. It is not evidence of forecasting skill. The real edge is the *coin selection*: concentrating on high-beta alts with enough intraday range to pay 1.5–2% per cycle dozens of times a month, at 3–30% of equity per position.

Main fragilities: (1) the exit only fills on an upward retracement, so a vol-crush leaves the ladder filled and the position stuck — visible as ~19 near-$0 days in Jun–Jul; (2) the ladder is buy-only, so a sustained downtrend means bounded-but-real averaging into a loser with an unreachable TP; (3) it's 100% long beta in a window when the universe went +43% to +218% — the same bot in a sustained alt downtrend has no rule in this data for it.

Caveat: the 2,000-fill cap hides everything before 2026-06-02. Funding records and the equity curve (Jan 28: $0 → $496) prove at least one earlier, unobserved phase.
