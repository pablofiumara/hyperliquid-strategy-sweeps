# Strategy description for this wallet — kilo-step-3.7-flash

## Strategy Mechanics

**Grid Structure Per Coin**
The bot places asymmetric bid/ask ladders: 2-4 buy orders below the mid-price and 1 sell order above it. Current open orders confirm this pattern across 7 active coins:

| Coin | Bids | Asks | Grid Spread |
|------|------|------|-------------|
| ZRO | 4 | 1 | 4.85% |
| ONDO | 3 | 1 | 7.48% |
| INJ | 2 | 1 | 13.30% |
| NEAR | 2 | 1 | 14.66% |
| HYPE | 2 | 1 | 10.70% |
| UNI | 1 | 1 | 22.59% |
| XMR | 1 | 1 | 19.36% |

**Position Sizing (Pyramiding)**
Buy sizes increase exponentially as price drops. Example for ZRO:
- Level 1 (closest to mid): 12.7 units @ $1.62
- Level 2: 18.6 units @ $1.58 (ratio 0.68)
- Level 3: 27.2 units @ $1.53 (ratio 0.68)
- Level 4 (furthest): 40.4 units @ $1.47 (ratio 0.67)

This is a ~33% size increment per level, creating a dollar-cost-averaging effect on dips.

## Coin Universe & Allocation

**Lifetime fills (140,000):**
- XMR: 35,350 fills ($1.94M volume)
- HYPE: 26,110 fills ($2.50M volume)
- NEAR: 20,650 fills ($1.52M volume)
- ZEC: 12,950 fills ($590K volume)
- INJ: 11,130 fills ($537K volume)
- ZRO: 11,060 fills ($344K volume)
- ONDO: 10,780 fills ($263K volume)
- JUP, UNI, XLM, ETH: remaining fills

**Focus:** Mid-cap altcoins with sufficient liquidity but not the most liquid majors (BTC/SOL absent from top activity).

## Performance Metrics

**30-day sample (2,000 fills):**
- Total PnL: $868.72 on $116,033 volume
- Per-coin returns: 0.26% (XMR) to 1.06% (ONDO) of volume
- Buy/Sell volume ratio: ~1.0 (balanced turnover)

**Lifetime closing trades (2,585 sampled):**
- Win rate: **99.4%** (2,570 wins / 15 losses)
- Median profit per closing trade: $0.99
- Mean profit per closing trade: $1.68
- Largest win: $23.68; Largest loss: -$8.20

**Overall:**
- Lifetime PnL: $60,810
- Current account value: $2,183
- Margin utilization: 62% ($1,354 of $2,183)
- No open positions (all positions closed between fills)

## Operational Patterns

- **Direction:** 74.2% buys / 25.8% sells (asymmetric grid with more buy levels)
- **Opening vs Closing:** Opens positions 2.87x more frequently than it closes them, indicating pyramiding accumulation
- **Time between fills:** 31-440 minutes per coin depending on volatility
- **Hours active:** Peak 08:00-15:00 UTC; lowest at 18:00 UTC; active across all 24 hours
- **Weekend activity:** ~50% of weekday volume (192 vs ~330 fills/day)
- **Order type:** Limit orders only (zero taker fees, consistent with grid/market-making)

## Strategy Summary

This is a **multi-coin grid trading bot with pyramiding position sizing**, characterized by:
1. Wide grid spacing (5-22%) per coin, tuned to individual volatility
2. Exponential position sizing (≈33% increment per level) for Martingale-style averaging
3. Near-instantaneous position turnover (fills and closes within minutes/hours)
4. Extreme win rate (99.4%) through small, frequent profits
5. Cross-margin futures deployment with ~62% capital utilization
6. No visible stop-loss mechanism; risk managed through wide grid spacing

The strategy profits from mean reversion in range-bound markets and is capital-efficient but vulnerable to strong directional breakouts where the pyramiding exposure could generate the occasional large loss (observed max: -$8.20).
