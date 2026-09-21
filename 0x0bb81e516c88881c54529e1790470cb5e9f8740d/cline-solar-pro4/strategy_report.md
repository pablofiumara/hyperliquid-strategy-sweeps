# Trading Strategy Report: 0x0bb81e516c88881c54529e1790470cb5e9f8740d

*Re-derived 2026-09-21 from the full, deduplicated fill history (see Methodology).*

## TL;DR

**A long-only, single-asset (HYPE-PERP) mean-reversion grid/martingale DCA bot** — almost certainly an automated script:

1. **Taker (market) buy** a base position of ~3.5-5 HYPE (~4% of margin equity; ~$90-340).
2. **Rest maker limit adds ~-1% lower**, size growing ~x1.85 per rung (0.5x first add), up to ~11 adds (max stack 280.8 HYPE).
3. **One reduce-only maker limit sells the ENTIRE stack at running average entry +0.84%** (order rewritten after each add).
4. Repeat. ~1,352 flat-to-flat cycles in ~11 months, **99.85% of cycles profitable**, +$5,486 closed PnL, no shorts, no stop-loss, no other coin ever.

## Verified snapshot (2026-09-21 09:47 UTC)

| Item | Value |
|---|---|
| Position | LONG 5.4 HYPE @ 95.7653 avg (3.6 taker @ 96.077 + 1.8 maker @ 95.142 — first add = 0.5x base at -0.97%) |
| Working exit | reduceOnly SELL 5.4 @ **96.57 = entry +0.840%** |
| Resting ladder bids (maker, GTC) | 11.52 @ 90.337 · 21.6 @ 88.415 · 39.6 @ 84.571 · 73.8 @ 80.727 · 138.6 @ 74.961 · 261 @ 69.195 (size step x1.875, gaps widening to -7.5%) |
| Margin | 10x cross; perp account value $4,240.92; withdrawable **$41.80** (capital fully committed) |
| Capital | spot USDC 8,121.80 (of which 4,240.70 held as perp margin) — total ~$8.1k; no other tokens |

## Full history (2025-10-13 → 2026-09-21)

- **4,896 fills**, 100% HYPE-PERP: 3,447 buys (Open Long) / 1,449 sells (Close Long); zero short fills, zero other coins, no spot trades.
- **closedPnl +$5,486.25** · fees $269.88 · funding **-$97.25** (486 hourly payments) -> net ~ +$5,119.
- **1,352 flat-to-flat cycles** (+1 currently open): **1,350 profitable / 2 losing = 99.85%**.
- Close fills: 1,446 positive / 3 negative. Best close +$107.59; worst -$2.79. 1,286/1,352 cycles (95%) close with a *single* sell fill; big stacks split into 2-8 fills (one order).
- Fill prices $23.32 - $96.12 (daily low $20.46 on 2026-01-20, while paused).
- Cadence: 3.9 cycles/day calendar (6.6 per active day, 204 active days); median cycle 64 min; one 42-day break 2025-12-25 -> 2026-02-05 (bot off through the bottom).
- Sizing step-up in Jun-2026: base entry raised from ~4% to ~8% of margin equity (~$170 -> ~$340 notional).

### Monthly closedPnl

| Month | PnL | Month | PnL |
|---|---|---|---|
| 2025-10 | +$264 | 2026-04 | +$177 |
| 2025-11 | +$373 | 2026-05 | +$511 |
| 2025-12 | +$363 | 2026-06 | **+$1,650** |
| 2026-01 | — (paused) | 2026-07 | +$403 |
| 2026-02 | +$260 | 2026-08 | +$713 |
| 2026-03 | +$404 | 2026-09 (to 21st) | +$369 |

## Inferred rules

1. **Universe:** HYPE-PERP only, long only; never shorts, hedges, or diversifies.
2. **Entry:** taker/market buy — 1,351 of 1,352 base entries were crossed. Base size 3.5-5 HYPE (~$90-340), ~4% of margin equity Oct-25 -> May-26, doubled to ~8% from Jun-26.
3. **Adds:** maker limit buys (1,743 maker / 350 taker), stacked a median **-1.01% below the previous fill** (deeper rungs -2%, -4.4%, -7%), size ladder **x1.85 per rung** after a 0.5x first add (consecutive-ratio modes: x0.5, x1.0, x1.75, x3.5; live ladder exactly x1.875). Max depth: 11 adds / 12 buys (2026-07-27). 57% of cycles add at least once; 43% are single-buy TP scalps.
4. **Exit:** a single full-stack **reduce-only maker limit at running average entry +0.84%** — mean +0.844%, median +0.840%, 1,219 cycles in the 0.8% bin; today's working order is entry x 1.0084 exactly. No scale-outs, no stop-loss orders.
5. **Order handling:** all GTC limits; grid maintained by cancel/replace; 99% of exit fills are maker. Only 3 negative closes in 11 months.
6. **Risk settings:** 10x cross margin; realized leverage ~1-2x typical, up to ~280 HYPE (~$8-12k notional) vs ~$4k margin equity; positions left open through deep drawdowns (see Risks).

## Two canonical cycles

**Scalp — 2026-09-20 (2 fills, +$2.90):** buy 3.72 @ 92.869 (taker) -> 2h37m later sell 3.72 @ 93.649 (maker) = +0.840%, then a new base buy immediately.

**Mega ladder — 2025-12-03 -> 07 (11 fills, +$69.94):** base 3.11 @ 36.19 (taker); adds 1.71 @ 35.83, 1.71 @ 35.47, 3.08 @ 34.74, 10.94 @ 34.02, 20.52 @ 33.29, 37.62 @ 31.85, 70.11 @ 30.40, 131.67 @ 28.23 (all maker); then ONE reduce-only sell of **280.78 HYPE @ 30.36** = VWAP +0.84%. The bot rode a -22% leg (36.19 -> 28.23) and still exited green.

## Risks / failure modes

- **No stop-loss.** The only exits are the TP or manual disposal: on 2025-12-25 the bot dumped a 10.68 stack at -1.68% (its one real loss, -$4.50) and went dark for 6 weeks.
- **Liquidation tail:** the currently resting ladder (down to 69.195 ~ -28%) would build a ~551 HYPE (~$38k) stack against ~$4.2k margin equity — a >30% HYPE flush without a bounce ends in a margin call. 10x cross leaves no room; withdrawable is already $41.80.
- **Funding drag:** -$97 total to date (negligible in an uptrend; grows if longs get crowded).
- **Edge profile:** profit is capped at ~+0.84% per cycle minus fees (fees ~ 5% of gross PnL); works in choppy/uptrending markets (HYPE $23 -> $96 over the sample) and depends on bounce frequency, not direction.

## Methodology & verification

- **Data:** Hyperliquid `/info`. Fills pulled with 3 paginated `userFillsByTime` calls (2,000 + 2,000 + 898 raw; API max 2,000/call, within the 5-page budget), deduplicated by `tid` -> 4,896 unique fills. Plus one-time `clearinghouseState`, `frontendOpenOrders`, `spotClearinghouseState`, `userFunding`, `portfolio`, and 1d `candleSnapshot`.
- **Reconstruction:** position rebuilt from `startPosition` + `side` on every fill (same-ms ties re-ordered for continuity: 235 swaps, 0 unresolved); cycles = flat -> flat; per-cycle VWAPs and PnL computed from fills only.
- **Cross-checks:** agrees with the independently derived reference in `agents.md` §7 — fills 4,896 vs 4,876 (trader still active; drift = new fills), closedPnl +$5,486 vs +$5,458, fees $270 vs $268, funding -$97.25 vs -$97, max win +$107.59 vs +$107.6, max stack 280.8 vs ~280 HYPE.
- **Correction note:** an earlier draft of this report (same run label) used offset-paginated `userFills` requests, where the API silently returned the same newest-2,000-fill page five times. Its 5x-inflated totals (+$17.2k / "10,000 fills") and "5-batch scale-out" reading were artifacts of that duplication; every number above is re-derived from the deduplicated history.
- Aggregated artifacts & scripts: `cline-solar-pro4/work/` (`fills_p0-2.json`, `fills_all.json`, `cycles_fixed.json`, `adds_analysis.json`, `summary.json`, `*.py`).
- These are hypotheses from public on-chain data, not financial advice; verify live before copying.
