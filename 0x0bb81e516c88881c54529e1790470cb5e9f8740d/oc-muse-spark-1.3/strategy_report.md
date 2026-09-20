# Strategy description for this wallet — oc-muse-spark-1.3

# source: final answer in output.txt

## TL;DR

Single-market, long-only, automated limit-grid martingale on **HYPE-PERP only**. No shorts, no spot, no other coin ever.

Logic: open small base long, add ~-1% lower in geometrically growing size, exit whole stack ~+0.84% above average entry via `reduceOnly` limit TP. Repeat 11 months. 99.8% win rate by design, tail-risk if HYPE trends down without bounce.

## Current snapshot (2026-09-20)

- Perps: `LONG 13.9 HYPE @ 92.1758`, `10x cross`, value `$1,265`, uPnL `-$15.6`, margin used `$126.5`, account value `$4,229`, withdrawable `$50.5`
- Spot: `8,082 USDC` (`4,219 hold`), no other tokens
- Open TP: `Sell 13.9 @ 92.95 reduceOnly`
- Open ladder bids (all `Limit GTC`, non-reduceOnly):
  - `11.71 @ 88.454 (~$1,035)`
  - `21.96 @ 86.572 (~$1,901)`
  - `40.26 @ 82.808 (~$3,333)`
  - `75.03 @ 79.044 (~$5,930)`
  - `140.91 @ 73.398 (~$10,342)`
  - `265.35 @ 67.752 (~$17,978)`

That is the fingerprint: sizes ~1.85x per step down, gaps -2% to -7% widening downward.

## Full history (2025-10-13 to 2026-09-20)

Paginated `userFillsByTime` in 30d chunks:

- `4,876 fills`, `100% HYPE`, `3,433 Open Long / 1,443 Close Long`, zero short fills
- `closedPnl +$5,458`, fees `$268`, funding `-$97` (485 records, all HYPE), net ~`+$5,090`
- Closes: `1,440 positive / 3 negative`, avg `+$3.78`, max `+$107.6` / `+$69.9`, min `-$3.1`
- `historicalOrders: 1,282 Limit only`, sells `203 all reduceOnly=True`, buys `1,079 reduceOnly=False`; `crossed=False (maker) 3,166 vs True (taker) 1,710`
- Profitable every active month, e.g. Oct25 `+$262`, Nov25 `+$375`, Dec25 `+$363`, Feb26 `+$256`, Mar26 `+$408`, Apr26 `+$177`, May26 `+$502`, Jun26 `+$1,640`, Jul26 `+$421`, Aug26 `+$713`, Sep (partial) `+$341`. Gap `2025-12-30 to 2026-01-29: 0 fills`.
- Price traded: `$23.32 to $94.15`, rode HYPE uptrend the whole period.

## Inferred rules

1. **Universe:** `HYPE-PERP` only. Never hedge.
2. **Entry:** base size ~2.8-3.4% of equity in notional — e.g. ~4 HYPE x $30 (~$120) when equity ~$3.5k in Dec25, now ~3.7 HYPE x $92 (~$340) on ~$12k total (spot+perp).
3. **Add:** on ~-1% adverse move. Measured over 2,086 adds: avg `-0.96%`, median `-1.01%`.
   - depth1: `-0.70%`, `~0.5x` (e.g. 3.73 + 1.86)
   - depth2-4: `-0.86% to -0.94%`, `~1.3-2.1x`
   - depth5+: `-1.6% to -3.2%`, `~2.5-3.5x`, up to 9-11 adds
4. **Exit:** full-stack limit TP at `avgEntry + 0.84%`. Measured over 1,443 cycles: avg `+0.843%`, recent 10 cycles exactly `+0.840%`. Yields `+$2.88` on base stack, `+$4.31` on 1.5x averaged stack at current prices.
5. **Leverage:** setting `10x cross`, actual low except drawdowns. Max reconstructed `~280 HYPE` (~$8k at $28-30) on ~$3.5k deposits = ~2-3x realized.
6. **Order handling:** GTC maker bids left resting, single reduceOnly TP rewritten after each fill. 640/490 open/canceled churn in recent `historicalOrders` window is cancel/replace grid maintenance.

## Two canonical examples

Micro (2026-09-18): `Buy 3.73 @92.367`, `Buy 1.86 @91.441 (-1.0%)`, `Sell 5.59 @92.832 +$4.32 (+0.84% vs VWAP)`. Then immediately `Buy 2.57 @92.922` new cycle.

Macro (2025-12-04/08 crash): `3.11 @36.18 -> 1.71 @35.83 -> 1.71 @35.47 -> 3.08 @34.74 -> 10.94 @34.02 -> 20.52 @33.29 -> 37.62 @31.85 -> 70.11 @30.40 -> 131.67 @28.23`, total `280.7 HYPE`, `Sell @30.36 +$69.94`. Survived `-22%` leg, `-36%` peak-to-trough from first entry. Same 12-17/19: `279.4 HYPE` low `23.32`, exit `24.63 +$57.79`. Only 3 losing closes in full sample (e.g. 2025-12-25 `-$1.71/-$2.79`), no hard stop.

Deposits show related-wallet funding (`0x5c7c...`, `0xafe6...`): in `2000+1500+1000+2000+1799+4149+3585`, out similar, so ROI on static capital cannot be computed cleanly — edge is per-cycle scalping, not buy-and-hold.

## Risks / when it breaks

- No stop, no short, no diversification. A >40-50% HYPE flush that fills full `$40k+` ladder on `$12k` equity = high cross-leverage / liquidation.
- Funding drag: persistent long paid `$97` total; negligible in uptrend, grows if crowded long.
- Capital inefficient, profits capped at ~0.84% per cycle; relies on bounce frequency. January 2026 inactivity = zero return when bot off / market flat.
- Copying requires mirroring ladder + TP exactly; naive market-following gets adverse fills and misses maker rebate.

This is consistent with a bot, not discretionary: fixed 0.84% TP, fixed -1% / 0.5x-2x add table, 11-month single-coin discipline, 100% Limit + reduceOnly sells. Not financial advice; verify live via `clearinghouseState` + `userFillsByTime` before copying.
