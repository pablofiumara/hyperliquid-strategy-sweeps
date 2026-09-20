# Trading Strategy Report: 0x0bb81e516c88881c54529e1790470cb5e9f8740d

## Executive Summary

This trader operates a **high-frequency grid/mean-reversion strategy** exclusively on HYPE perpetual futures. Over 121 days (May 22 - Sep 20, 2026), they executed 10,000 fills with a 100% win rate on closed positions and +17,185.63 USDC in realized profits.

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Fills Analyzed | 10,000 |
| Trading Period | 2026-05-22 to 2026-09-20 |
| Duration | 121 days |
| Trading Days | 108 |
| Assets Traded | 1 (HYPE only) |
| Total Realized PnL | +17,185.63 USDC |
| Total Fees Paid | 843.39 USDC |
| Fee/PnL Ratio | 4.91% |
| Win Rate (closed positions) | 100% (2,975/2,975) |
| Avg Trades/Day | 92.6 (median: 62.5) |
| Max Trades/Day | 425 (June 5, 2026) |

---

## Strategy Summary

**Strategy Type**: Grid/Mean-Reversion Long-Only Bot with DCA entries and scale-out exits

**Core Mechanics**:
1. Buy limit orders at predetermined price levels below market (grid/DCA)
2. Build positions incrementally as price drops (averaging down)
3. Scale out in equal batches when price rises (locking profits)
4. Never short - only long positions


## Trade Direction & Side Distribution

| Action | Count | % |
|--------|-------|---|
| Buy / Open Long | 7,025 | 70.25% |
| Sell / Close Long | 2,975 | 29.75% |
| Short trades | 0 | 0% |

**Key observation**: The trader is purely long-only. The ratio of opens to closes (7025:2975 ≈ 2.36:1) indicates positions are built up faster than they are closed, suggesting either:
- Positions held for longer durations
- Unclosed losing positions (hidden risk)
- Ongoing accumulation

---

## Position Building Pattern (Scale-In / DCA)

The trader builds positions by buying in batches at declining price levels:

```
Early trades (May 22, 2026) - Building a position:
  Layer 1: 1.38 units × 5 buys @ 61.26 (total: 6.9 units)
  Layer 2: 1.38 units × 5 buys @ 60.64 (total: 6.9 units)
  Layer 3: 2.48 units × 5 buys @ 60.02 (total: 12.4 units)
  Layer 4: 2.48 units × 5 buys @ 59.40 (total: 12.4 units)
  Layer 5: 8.80 units × 5 buys @ 58.16 (total: 44.0 units)
  Layer 6: 16.50 units × 5 buys @ 56.93 (total: 82.5 units)
  Layer 7: 30.25 units × 5 buys @ 54.45 (total: 151.25 units)
  → Position built to ~316 units, averaging down from 61.26 to 54.45
```

**Pattern observed**:
- 5 identical fills per price level (suggests grid configuration with batch execution)
- Position size increases at lower prices (30.25 units vs 1.38 units)
- Aggressive buying as price declines (confident mean-reversion bet)

---

## Position Exiting Pattern (Scale-Out)

```
First exit after building position:
  Closed 66.02 units × 5 sells @ 57.02 = 330.1 units total
  Realized PnL: +31.66 per batch (total: +158.30)
```

**Exit characteristics**:
- Equal-sized batches for exits (mirrors entry structure)
- All exits are profitable (100% win rate)
- Exit size (10.28 mean) > entry size (4.35 mean), suggesting accumulation before exit

---

## Trade Sizing Distribution

| Size Bucket | Fills | % of Total |
|-------------|-------|------------|
| < 1 units | 665 | 6.65% |
| 1-2 units | 755 | 7.55% |
| 2-5 units | 5,180 | 51.80% |
| 5-10 units | 2,330 | 23.30% |
| 10-50 units | 950 | 9.50% |
| 50+ units | 120 | 1.20% |

- **Mean size**: 6.12 units
- **Median size**: 4.14 units
- **Min size**: 0.01 units
- **Max size**: 221.61 units

---

## Order Types

| Type | Count | % |
|------|-------|---|
| Crossed (market) | 3,545 | 35.45% |
| Non-crossed (limit) | 6,455 | 64.55% |

Majority of fills are limit orders, indicating the trader either:
- Provides liquidity to the market
- Uses resting limit orders for entries/exits
- Benefits from maker fee rebates

---

## PnL Analysis (Closed Positions Only)

| Metric | Value |
|--------|-------|
| Profitable closes | 2,975 (+17,185.63 USDC) |
| Losing closes | 0 (0.00 USDC) |
| Zero PnL closes | 0 |
| Avg profit per close | +5.78 USDC |
| Median profit per close | +2.95 USDC |
| Max single close PnL | +107.59 USDC |
| Min single close PnL | +0.04 USDC |

**Note**: 7,025 open positions remain unclosed. The true strategy performance may differ if these positions are closed at a loss.

---

## Daily Performance (Top 10 Days)

| Date | Fills | PnL | Fees |
|------|-------|-----|------|
| 2026-06-05 | 425 | +835.26 | 38.80 |
| 2026-08-21 | 335 | +380.23 | 20.84 |
| 2026-08-19 | 330 | +440.66 | 22.49 |
| 2026-08-22 | 320 | +528.37 | 25.93 |
| 2026-06-07 | 290 | +423.49 | 22.96 |
| 2026-06-25 | 280 | +408.36 | 21.10 |
| 2026-06-03 | 265 | +424.84 | 22.96 |
| 2026-06-16 | 260 | +390.81 | 22.06 |
| 2026-06-11 | 250 | +431.17 | 19.22 |
| 2026-05-29 | 245 | +299.70 | 18.08 |

High-volume days show strong PnL, suggesting the strategy benefits from volatility.

---

## Price Action Context

| Metric | Value |
|--------|-------|
| Entry price range | 54.45 - 94.125 |
| Exit price range | 57.02 - 94.06 |
| Overall price range (trades) | 54.45 - 94.125 |
| Mean entry price | ~74 (estimated from filled orders) |
| Mean exit price | ~76 (estimated from filled orders) |

The trader bought aggressively in the 54-61 range and took profits in the 57-94 range.

---

## Inferred Strategy Logic

### Entry Trigger
- **Grid-based**: Places limit buy orders at regular price intervals below current market
- **Threshold-based DCA**: Increases order size as price moves further from entry
- **5-batch execution**: Each grid level uses 5 identical orders (possibly to average fill price)

### Exit Trigger
- **Profit targets**: Sells when price rises to predetermined levels
- **Scale-out**: Exits in batches matching entry structure
- **No stop-loss visible**: All closes are profitable; losing positions may be held open

### Risk Profile
- **Unrealized risk**: 4,050 unclosed fills could represent losing positions
- **Low fee drag**: Only 4.91% of profits consumed by fees
- **concentration risk**: Single-asset strategy (HYPE only)

---

## Data Sources & Methodology

- **API**: Hyperliquid `/info` endpoint with `userFills` query
- **Trader**: `0x0bb81e516c88881c54529e1790470cb5e9f8740d`
- **Pages fetched**: 5 pages × 2,000 fills = 10,000 total fills
- **Aggregation**: Local Python analysis in work directory
- **Raw data files**: `fills_page_{0-4}.json`

---

*Report generated: 2026-09-20*
*Analyst: Strategy Analysis Bot*
