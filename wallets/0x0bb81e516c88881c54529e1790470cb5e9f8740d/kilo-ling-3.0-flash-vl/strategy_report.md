# Strategy description for this wallet — kilo-ling-3.0-flash-vl

# source: final answer in output.txt

## Overview

| Metric | Value |
|--------|-------|
| **Asset** | HYPE Perpetual (Hyperliquid) — exclusively |
| **Direction** | Long-only (0 shorts across 2,000 fills) |
| **Total Fills** | 2,000 (1,405 opens, 595 closes) |
| **Realized PnL** | $3,428.49 |
| **Time Active** | ~10 days (timestamps: 1779457268 → 1789872845) |
| **Maker Ratio** | 64.5% (1,291) vs Taker 35.5% (709) |
| **Total Fees** | $168.45 |
| **Median PnL/Close** | $2.95 |
| **Mean PnL/Close** | $5.76 |

---

## Strategy 1: Tiered Limit Order Ladder (Primary)

The trader's **current open orders** reveal a structured accumulation ladder:

| Tier | Side | Price | Size (HYPE) | Notional |
|------|------|-------|-------------|----------|
| 0 | Ask (reduce-only) | $92.95 | 13.9 | $1,292 |
| 1 | Bid | $88.454 | 11.71 | $1,085 |
| 2 | Bid | $86.572 | 21.96 | $1,901 |
| 3 | Bid | $82.808 | 40.26 | $3,330 |
| 4 | Bid | $79.044 | 75.03 | $5,930 |
| 5 | Bid | $73.398 | 140.91 | $10,341 |
| 6 | Bid | $67.752 | 265.35 | $17,978 |

**Key characteristics:**
- **Exponentially decreasing sizes** as price increases — each tier up is ~1.85× smaller
- **Consistent price increments** within ranges (~$1.88 between top tiers, ~$3.76 mid-tier, ~$5.65 bottom tier)
- **Total bid notional**: ~$40,522 across 555 HYPE
- **Reduce-only sell at $92.95**: Acts as a hard take-profit ceiling for 13.9 HYPE

This is a **dollar-cost-averaging-into-longs** approach: the trader commits more capital at lower prices and progressively less at higher prices, creating a weighted average entry well below mid-market.

---

## Strategy 2: Pyramiding Position Building

Analysis of the `startPosition` field reveals a **pyramiding** approach where the trader accumulates positions progressively:

Example position build sequence:
```
startPos=0.0  → open 3.66 HYPE @ $94.125  (position: 3.66)
startPos=3.66 → open 1.83 HYPE @ $93.159  (position: 5.49)
startPos=5.49 → open 1.83 HYPE @ $92.218  (position: 7.32)
startPos=7.32 → open 3.29 HYPE @ $91.277  (position: 10.61)
```

The trader **adds to winning/losing positions** as price moves, with position sizes growing at lower price levels (more aggressive accumulation on dips).

---

## Strategy 3: Multi-Level Profit Taking

Exits are staggered across three tiers:

| Tier | PnL Range | Count | Avg PnL | Description |
|------|-----------|-------|---------|-------------|
| Small | $0–$3 | 320 | $2.41 | Quick scalps on small positions |
| Medium | $3–$10 | 199 | $5.21 | Partial exits on medium positions |
| Large | $10+ | 76 | $21.34 | Full exits on large positions |

The largest single close was **221.61 HYPE at $58.336, realizing $107.59**.

---

## Strategy 4: Liquidation Hunting / Front-Running

The trader has **8 liquidation events** where they liquidated other traders:

| Liquidated User | Mark Price |
|----------------|------------|
| 0xc64211d5... | $77.39 |
| 0x37f2af56... | $62.25 |
| 0x954b6de2... | $60.189 |
| 0xd745e55d... | $65.289 |
| 0xa0d91cbaa... | $61.188 |
| 0xc9b74f14... | $70.008 |
| 0xcd9d3b2d... | $58.642 |
| 0xe50681d3... | $63.867 |

This suggests the trader monitors liquidation thresholds and actively triggers liquidations when positions are near critical levels — a secondary profit source.

---

## Summary of Strategies

1. **Primary — Limit Order Ladder Accumulation**: Structured tiered buy orders with exponentially decreasing sizes, committing ~$40K notional across 6 price levels. This is the core entry mechanism.

2. **Secondary — Pyramiding**: Progressive position building where the trader adds to existing positions as price moves, with size scaling based on price level (larger adds at lower prices).

3. **Tertiary — Multi-Level Profit Taking**: Staggered exits at three PnL tiers (small scalps, medium partial exits, large full exits), managing risk through distributed take-profits.

4. **Supplementary — Liquidation Hunting**: Active monitoring and triggering of other traders' liquidations for additional profit.

**Risk Profile**: The strategy is long-biased with a structured entry ladder that provides a weighted average cost basis well below market. The reduce-only sell at $92.95 caps upside on the current position. The 64.5% maker ratio indicates patience and limit-order discipline. Total fees of $168 against $3,428 PnL yields a ~95% fee-adjusted return.
