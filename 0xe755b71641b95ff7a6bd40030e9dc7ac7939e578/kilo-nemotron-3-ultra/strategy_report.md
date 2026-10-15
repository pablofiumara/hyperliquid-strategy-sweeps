# Trading Strategy Analysis: 0xe755b71641b95ff7a6bd40030e9dc7ac7939e578

## Executive Summary
This trader operates a **multi-coin, long-biased swing/position trading strategy** with strong market-making characteristics. They accumulate positions across 11 altcoins using predominantly maker orders (71% buys, 82% sells), hold for weeks (median ~9 days), and consistently realize profits across all assets. The strategy combines **trend-following accumulation** with **passive liquidity provision**.

---

## Portfolio Composition (11 Coins)

| Coin | Volume | Buys/Sells | Avg Hold | Realized PnL | Current Position |
|------|--------|------------|----------|--------------|------------------|
| HYPE | $107K | 777/342 | ~9 days | +$1,022 | 3.51 @ $94.94 |
| XMR | $83K | 1,209/306 | ~9 days | +$316 | 0.351 @ $604 |
| NEAR | $65K | 657/228 | ~9 days | +$649 | 77.8 @ $5.02 |
| ZEC | $25K | 435/120 | ~9 days | +$65 | - |
| INJ | $23K | 342/135 | ~9 days | +$167 | 29.0 @ $8.36 |
| ZRO | $15K | 312/162 | ~9 days | +$111 | 14.9 @ $1.66 |
| ONDO | $11K | 339/123 | ~9 days | +$119 | 145 @ $0.557 |
| UNI | $6K | 144/48 | ~9 days | +$66 | 13.0 @ $10.42 |
| JUP | $8K | 168/66 | ~9 days | +$59 | - |
| XLM | $3.6K | 51/18 | ~9 days | +$31 | - |
| ETH | $0.4K | 15/3 | ~9 days | +$1 | - |

**Total Realized PnL (6000 fills): ~$2,600+**
**Current Open Positions: ~$1,353 notional (62% of $2,181 account)**
**Current Unrealized PnL: -$66.5**

---

## Core Strategy Mechanics

### 1. **Accumulation + Distribution Pattern**
- **Buy:Sell ratio = 2.86:1** (4,449 buys vs 1,551 sells in 6000 fills)
- **Scaling in small, scaling out large**: Avg sell size 2-3x avg buy size across all coins
- **Consecutive buys up to 24**, consecutive sells up to 12 — trend-following accumulation
- **Position sizing trends**: Most coins show decreasing buy size over time (taking profits into strength), except HYPE and XMR (increasing conviction)

### 2. **Market-Making / Passive Execution**
- **71% of buys are maker (non-crossed)**, 82% of sells are maker
- **Zero TWAP orders** — all manual/algo limit orders
- Earns spread + rebates while building positions
- Typical trade size: **Median $36, Mean $58** — small, frequent clips

### 3. **Long Hold Horizons**
- **Median hold: ~9 days (12,600 min)**
- **Mean hold: ~24 days (34,000 min)**
- **99.4% of closed positions held >24 hours**
- This is **not scalping or day trading** — it's swing/position trading

### 4. **Multi-Coin Diversification**
- 11 active coins, all profitable
- Concentration: HYPE (32% vol), XMR (25%), NEAR (19%) = 76% of volume
- Long-tail: ZEC, INJ, ZRO, ONDO, UNI, JUP, XLM, ETH
- **No short positions observed** — exclusively long-biased

### 5. **Funding Carry Component**
- **Pays funding on most longs** (negative funding rates)
- **Receives funding on INJ** (negative funding rate = shorts pay longs)
- Net funding cost is small relative to trading PnL
- Positions held long enough for funding to matter but not dominant

---

## Risk Management

| Metric | Value |
|--------|-------|
| Max leverage | 1x (cross margin only) |
| Position concentration | Max ~24% per position (HYPE $325/$1,353) |
| Account utilization | 62% deployed |
| Stop losses | None visible (mental/unpublished) |
| Drawdown control | Scaling out reduces exposure progressively |

**Key insight**: No leverage, no liquidation risk. Pure spot-style perp trading with 1x cross margin.

---

## Daily Activity Profile

- **Trades/day**: 20-350 (avg ~150)
- **Volume/day**: $2K-$12K
- **Peak hours**: 12-13 UTC (129 trades), 13-14 UTC (152 trades)
- **Active 24/7**: Trades every hour, lower volume 18-23 UTC
- **Consistent profitability**: Positive PnL on 28/30 recent days

---

## PnL Drivers (Decomposed)

1. **Directional beta**: Long altcoins in uptrend (HYPE +$1K, NEAR +$649, INJ +$167)
2. **Spread capture**: Maker rebates + passive fills (~$73 total fees paid on $348K volume = 2.1 bps)
3. **Timing skill**: Buys lower than sells on 10/11 coins (HYPE exception = accumulation)
4. **Position management**: Scaling out at better prices than average entry

**HYPE anomaly**: Avg buy $76.96 > avg sell $73.99 (-3.86% edge) but still +$1,022 PnL
→ Accumulating core position, not trading for spread

---

## Strategy Classification

**Primary**: **Multi-asset Swing Accumulation with Passive Execution**
- Builds core positions in 11 altcoins over weeks
- Uses limit orders to earn spread
- Takes partial profits on rallies (large sells)
- Re-accumulates on dips (many small buys)

**Secondary**: **Funding-Aware Carry**
- Holds positions through funding periods
- Selects coins where funding cost < expected appreciation
- INJ provides positive carry (negative funding rate)

**Not**: HFT, scalping, day trading, directional leverage, basis trading, arb, TWAP execution

---

## Replicable Rules (Algorithmic Translation)

```
UNIVERSE = [HYPE, XMR, NEAR, ZEC, INJ, ZRO, ONDO, UNI, JUP, XLM, ETH]

FOR each coin in UNIVERSE:
    TARGET_ALLOCATION = risk_budget[coin]  # ~5-25% each
    
    # ACCUMULATION PHASE (continuous)
    WHILE position < TARGET_ALLOCATION:
        PLACE MAKER BUY at bid - 1-3 bps
        SIZE = min(remaining_allocation, $30-70 clips)
        MAX_CONSECUTIVE_BUYS = 24
    
    # DISTRIBUTION PHASE (on rally)
    IF price > entry * 1.02 AND position > 0:
        PLACE MAKER SELL at ask + 1-3 bps
        SIZE = position * 0.2-0.5 (2-3x buy size)
        MAX_CONSECUTIVE_SELLS = 12
    
    # REBALANCE
    DAILY: rebalance toward target allocations
    WEEKLY: review funding costs vs carry
    
RISK CONTROLS:
    LEVERAGE = 1x CROSS ONLY
    MAX_DRAWDOWN_PER_COIN = 15%
    NO_STOP_ORDERS (mental exits only)
```

---

## Key Differentiators vs Typical Retail

| Aspect | This Trader | Typical Retail |
|--------|-------------|----------------|
| Leverage | 1x | 10-50x |
| Order type | 75%+ Maker | 90%+ Taker |
| Hold time | 9-24 days | Minutes-hours |
| Diversification | 11 coins | 1-3 coins |
| PnL consistency | 28/30 days green | High variance |
| Position mgmt | Scale in/out | All-in/all-out |
| Funding awareness | Yes (INJ carry) | Ignored |

---

## Conclusion

This is a **sophisticated, disciplined portfolio trader** treating Hyperliquid perps as spot-with-funding. They:
1. **Provide liquidity** (maker-heavy) while building positions
2. **Diversify broadly** across liquid altcoins
3. **Manage positions professionally** (scale in/out, no leverage)
4. **Exploit funding asymmetry** (INJ negative funding)
5. **Compound steadily** (~$2.6K realized on ~$350K volume = 0.74% net return over ~4 months)

The strategy is **replicable, scalable, and low-risk** — suitable for algorithmic implementation with proper position sizing and risk limits.