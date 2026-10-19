# Strategy description for this wallet — oc-mimo-v2.5

# source: final answer in output.txt

ACCOUNT STATS:
  Current value: $4,229.92
  Position: 13.9 HYPE @ $92.18 avg ($1,266.23)
  Leverage: 10x cross
  Withdrawable: $51.10

HISTORICAL PERFORMANCE:
  Total fills: 2,000
  Total realized PnL: +$3,428.49
  Total fees: $168.45
  Net PnL: +$3,260.04
  Time period: May 22 - Sep 19, 2026 (121 days)
  Avg fills/day: 16.6

STRATEGY IDENTIFICATION:

1. DCA + GRID TRADING (Primary)
   - Accumulates HYPE through small, repeated buys
   - Avg buy size: 4.35 HYPE ($300-$400)
   - 59.4% of buys are 1-5 HYPE (micro-lots)
   - Sells in small chunks as price rises
   - 537 Sell->Buy grid pairs detected
   - Consistent ~$1.42 profit per grid cycle

2. DCA ACCUMULATION (Secondary)
   - 200 streaks of 3+ consecutive buys
   - Buys at decreasing prices (avg 3.46% drop)
   - 131 buy streaks with >2% price drops
   - Classic dollar-cost averaging into weakness

3. SCALPING (Minor)
   - 25 Buy->Sell scalp pairs detected
   - Avg profit: 1.3% per scalp
   - Short holding periods (<2 min)

PATTERN SUMMARY:
   - Opens LONG positions, closes LONG positions
   - 1,405 Open Long trades (buys)
   - 595 Close Long trades (sells)
   - Buy/Sell ratio: 2.36x (net accumulator)
   - 8 liquidations over 4 months (high risk periods)

RISK PROFILE:
   - High leverage (10x cross)
   - Single asset concentration (HYPE only)
   - 29.9% of account in position
   - Active during US market hours (10:00-12:00 peak)

## Trading Strategy Analysis: `0x0bb8...740d` on Hyperliquid

### Overview
This trader runs a **single-asset DCA + Grid Trading strategy** exclusively on **HYPE** (Hyperliquid's native token) using **10x cross leverage**.

### Core Strategy: DCA Grid Trading
1. **Accumulation Phase**: Buys 1–5 HYPE in small increments as price drops (200 streaks of 3+ consecutive buys, avg 3.46% price decline per streak)
2. **Distribution Phase**: Sells in small chunks as price recovers (595 total sells)
3. **Grid Cycle**: 537 sell→buy pairs detected within 2-minute windows, capturing ~0.02–0.84% spreads per cycle
4. **Avg profit per grid cycle**: ~$1.42

### Key Metrics
| Metric | Value |
|---|---|
| Total fills | 2,000 |
| Realized PnL | +$3,428.49 |
| Fees paid | $168.45 |
| Net PnL | +$3,260.04 |
| Time span | 121 days (May 22 – Sep 19, 2026) |
| Avg fills/day | 16.6 |
| Buy/Sell ratio | 2.36x (net accumulator) |
| Liquidations | 8 |

### Risk Profile
- **10x cross leverage** on a single asset
- **29.9% of account** currently in HYPE position ($1,266 of $4,230)
- **8 liquidations** over 4 months (occasional blowups)
- Peak activity during **US market hours** (10:00–12:00 UTC)

### Pattern Summary
- Opens LONG (buys): 1,405 trades
- Closes LONG (sells): 595 trades
- The strategy is a **net accumulator** — building a HYPE position over time while scalping grid profits along the way
- Small, frequent trades suggest **automated/bot-driven** execution
