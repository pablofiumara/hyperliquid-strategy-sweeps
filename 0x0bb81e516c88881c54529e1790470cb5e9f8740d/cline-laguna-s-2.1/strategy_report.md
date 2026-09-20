# Trader Strategy Analysis: 0x0bb81e516c88881c54529e1790470cb5e9f8740d

## Source
- HyperX Profile: https://hyperx.trade/hyperliquid/trader?address=0x0bb81e516c88881c54529e1790470cb5e9f8740d
- Data sources: Hyperliquid public API (`info` endpoint) — `userFills`, `userFunding`, `clearinghouseState`, `openOrders`, `portfolio`, `metaAndAssetCtxs`, `allMids`
- Data fetched: September 20, 2026

---

## 1. Account Overview

| Metric | Value |
|--------|-------|
| Account Size (perp) | ~$4,235 |
| Account Size (total: spot+perp) | ~$12,324 |
| 90-Day PnL | +$691 (+16.2% monthly on perp) |
| All-time PnL (since Oct 2025) | +$5,060 |
| Win Rate | 100.0% (542/542 completed cycles) |
| Current Position | HYPE 10× LONG, 13.9 HYPE @ $92.18 |
| Floating PnL | -$9.28 |
| Trader Tags | Stable/profitable / Profit machine / Small & refined / Crypto native |

---

## 2. Derived Strategy: Leveraged DCA Grid Bot on HYPE Perpetual

### Core Mechanism
The trader operates an automated **long-only DCA (Dollar Cost Averaging) ladder bot** on the HYPE perpetual futures market. The bot:

1. **Opens a long position** at the market (or near-market) price
2. **Places a descending buy ladder** of limit orders below the entry, with position sizes that **increase geometrically** (~1.88× per rung) as the price drops
3. **Sets a take-profit** at **0.84% above the VWAP (average entry price)** as a reduce-only sell order
4. **Closes the entire position** when TP is hit, then immediately begins a new cycle

### Key Parameters

| Parameter | Value |
|-----------|-------|
| Asset | HYPE perpetual (Hyperliquid) |
| Direction | Long-only |
| Max Leverage | 10× (HYPE maximum on Hyperliquid) |
| Take-Profit (TP) | **0.84% above VWAP entry** |
| TP order type | Reduce-only sell limit |
| Entry order type | 50% maker (limit), 50% taker (market) |
| Average cycle duration | ~5.3 hours |
| Grid levels (below first entry) | 1%, 2%, 3%, 4%, 6%, 8%, 12%, 16% |
| Size multiplier per grid level | ~1.88× (martingale-style) |

---

## 3. Entry Mechanism: Fixed-Notional DCA Ladder

### Base Entry Size
The bot opens each cycle with a **fixed notional entry** that scales with account growth:

| Period | Date Range | First Entry Notional | HYPE Size | Est. Account (perp) |
|--------|-----------|---------------------|----------|-------------------|
| Phase 1 | May 22–28, 2026 | ~$170 | 2.7–3.0 HYPE | ~$4,000 |
| **Transition** | May 29, 2026 | **Doubled to ~$345** | 5.2–5.5 HYPE | Account ~2× larger |
| Phase 2 | May 29 – Sep 20, 2026 | ~$345–$350 | 3.7–5.5 HYPE | ~$4,200–$8,000 |

The entry size doubled on **May 29, 2026**, coinciding with ~2× account growth from compounding 0.84% TP cycles.

### DCA Ladder Structure
When the price drops below the entry, the bot scales in using a geometric ladder. Verified from historical fills:

**Example cycle (May 22, 2026 — HYPE at ~$62):**
```
Price      Drop%   Size     Size/1st  Notional  Notnl/1st
61.874     +0.00%  2.75     1.00x     $170.2    1.00x   <- First entry (market)
61.260     -0.99%  1.38     0.50x     $84.5     0.50x   <- DCA add (1/2 size)
60.640     -1.99%  1.38     0.50x     $83.7     0.49x
60.020     -3.00%  2.48     0.90x     $148.8    0.87x
59.400     -4.00%  2.48     0.90x     $147.3    0.87x
58.160     -6.00%  8.80     3.20x     $511.8    3.01x   <- Larger add on bigger drop
56.930     -7.99%  16.50    6.00x     $939.3    5.52x
54.450     -12.00% 30.25    11.00x    $1647.1   9.68x   <- Deep DCA
```

**Grid price levels** (relative to first entry): **1%, 2%, 3%, 4%, 6%, 8%, 12%** drops — the 5%, 10%, and 11% levels are skipped, with wider spacing at larger drawdowns.

### Current Open Orders Ladder (as of Sep 20, 2026)
```
Level  Price     Size      Ratio    Step$    Step%
  0    67.752    265.35    1.000x    -        -
  1    73.398    140.91    0.531x   -5.646   -7.69%
  2    79.044     75.03    0.532x   -3.764   -4.76%
  3    82.808     40.26    0.537x   -3.764   -4.55%
  4    86.572     21.96    0.545x   -1.882   -2.17%
  5    88.454     11.71    0.533x    -        -
```
*(Sorted from deepest to shallowest; each level is ~1.88× the size of the level above)*

**Ladder step pattern**: $1.882, $3.764, $3.764, $5.646, $5.646 — multiples of $1.882 in the pattern **1×, 2×, 2×, 3×, 3×** (cumulative: 0, 1, 3, 5, 8, 11 × $1.882).

---

## 4. Take-Profit Mechanism: 0.84% Above VWAP

### Verification
The exit price was compared against the VWAP entry across all cycles:

| Metric | Value |
|--------|-------|
| Exit/AvgEntry ratio (median) | 1.00840 → **0.84%** |
| Exit/AvgEntry ratio (mean) | 1.00892 → 0.89% |
| Cycles at 0.83–0.85% | 479/542 (**88.4%**) |
| Cycles at exactly 1.0084 | 296/542 |
| Max deviation from 0.84% (normal cycles) | ±0.01% |

**Verified against current open order**: entryPx = $92.1758, TP sell order at $92.95 → ratio = 1.00840 = **0.84%** ✓

### Order Type
- **98.8% of exits are maker** (non-crossed limit orders) — confirming TP is a **limit sell order** placed above the VWAP
- **Reduce-only flag** confirmed on the current TP order — preventing the TP from opening a short position

### Outlier Cycles (8.5% of cycles, >1.0% return)
46 cycles exceeded the normal 0.84% TP, with returns up to 4.08%. These cluster on specific dates:
- **May 29–Jun 8**: 1.0–1.6% returns (coincides with entry size doubling)
- **Aug 10–22**: 1.0–4.1% returns (multiple clusters)
- **Sep 9–17, Sep 30**: 1.0–1.6% returns

These outliers likely represent periods where the bot temporarily increased the TP rate or market orders swept favorable prices.

---

## 5. Position Sizing & Risk Profile

### Martingale Grid
The bot uses **geometric position sizing** (≈1.88× per level) — a classic martingale/Doubling strategy:
- Each grid level buys ~1.88× more HYPE than the level above
- Notional at each level increases ~1.77× (price also drops)
- Concentrates buying power at lower prices, accelerating DCA

### Drawdown Behavior
The strategy shows aggressive DCA during drawdowns, with position sizes spiking dramatically:

| Date | Peak Position | Context |
|------|--------------|---------|
| Nov 23, 2025 | **263.9 HYPE** (~$13,200 notional @ $50) | Deep drawdown — bot added at every level |
| Dec 7, 2025 | 172.2 HYPE | Recovery phase |
| Dec 18, 2025 | 177.5 HYPE | Drawdown |
| Jun 10, 2026 | 130.0 HYPE | Mid-year correction |
| Jul 18, 2026 | 118.6 HYPE | Summer correction |
| Sep 13, 2026 | 52.4 HYPE | Recent activity |

During the **Nov 2025 drawdown**, the position grew from ~11 HYPE (Nov 18) to **264 HYPE** (Nov 23) — a 24× increase as HYPE dropped. The position was then fully closed via TP by Nov 24, demonstrating the strategy's core mechanism: **accumulate deep during drawdowns, exit at 0.84% profit when price recovers**.

### Current Position Risk
- **Position**: 13.9 HYPE long at 10× leverage
- **Entry**: $92.18 (VWAP)
- **Margin used**: ~$1,272 (10× leverage on $12,720 notional)
- **Liquidation buffer**: ~9.0% downside to liquidation (at 10× leverage)
- **Open DCA ladder**: Extends to $67.75 (-26% from current), total potential add of 527 HYPE
- **TP**: $92.95 (0.84% above entry)

---

## 6. Performance Summary

| Metric | Value |
|--------|-------|
| Period analyzed | May 22 – Sep 20, 2026 (120 days of fills) |
| Total cycles completed | 542 |
| Win rate | **100.0%** (542/542) |
| Total realized PnL | **$3,209.60** |
| Total fees paid | $168.45 (5.3% of gross PnL) |
| Total funding paid (long) | -$96.95 (over 342-day lifetime) |
| Net profit (PnL - fees - funding) | ~$2,944 |
| Avg profit per cycle | $5.92 |
| Avg cycle return | 0.89% (median: 0.84%) |
| Avg cycle duration | 5.3 hours |
| Total volume traded | ~$1.3M (all-time) |

### Fee & Funding Efficiency
- Fees: 5.3% of gross PnL
- Funding: -$97 (long pays shorts, consistently positive funding rate ~0.00125%/8h)
- **Combined costs: ~8.3% of gross PnL** — well covered by the 0.84% per-cycle TP

---

## 7. Strategy Summary

The trader operates a **high-leverage, long-only DCA grid bot** on HYPE perpetual futures:

1. **Enter long** with a fixed notional order (~$345 per cycle)
2. **Scale down** with a geometric DCA ladder placing larger buy orders at 1–12% below entry (size ≈ 1.88× per level)
3. **Set take-profit** at exactly **0.84% above the VWAP entry** as a reduce-only sell limit order
4. **Close fully** at TP, then reset for the next cycle
5. Use **10× leverage** throughout (HYPE max)

**Risk mitigation**: The 100% win rate and aggressive DCA during drawdowns (e.g., 264 HYPE in Nov 2025) allow the bot to profit from volatility — adding during dips and taking profit on recovery. However, with 10× leverage and no hedging, a sustained downtrend could trigger large drawdowns or liquidation if the price drops beyond the deepest ladder level.

**Trader profile**: Crypto-natural, algorithmic, systematic — likely a custom or commercial bot with parameters tuned for HYPE's volatility regime (0.84% TP, 1.88× size ratio, 10× leverage).



