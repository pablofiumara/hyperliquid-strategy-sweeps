# Strategy description for this wallet — unverified-kilo-ling-3.0-flash-fin

Based on my independent analysis of the Hyperliquid on-chain data for address `0x0bb81e516c88881c54529e1790470cb5e9f8740d`, here is the derived trading strategy:

---

## Strategy: **HYPE Grid DCA (Dollar Cost Averaging)**

### Core Profile
- **Single asset**: 100% HYPE — all 2,000 fills across 112 trading days are exclusively HYPE
- **Direction**: Long-biased — 1,409 buys (70.5%) vs 591 sells (29.5%)
- **Order type**: All Limit orders, GTC (Good Till Canceled) — no market orders, no TWAP
- **Account value**: $8,193.34 | All-time perp PnL: $5,188.22 | All-time volume: $1,328,785.82

### Grid Structure
The trader maintains a **7-level buy limit order grid** below the current market price (~$93):

| Level | Price | Size (HYPE) | Gap from Prev | Size Ratio |
|-------|-------|-------------|---------------|------------|
| 1 | $67.68 | 268.98 | — | — |
| 2 | $73.32 | 142.84 | $5.64 | 0.53x |
| 3 | $78.96 | 76.05 | $5.64 | 0.53x |
| 4 | $82.72 | 40.81 | $3.76 | 0.54x |
| 5 | $86.48 | 22.26 | $3.76 | 0.55x |
| 6 | $88.36 | 11.87 | $1.88 | 0.53x |
| 7 | $90.24 | 3.34 | $1.88 | 0.28x |

- **Size decay ratio**: ~0.53x per level (geometric decrease)
- **Price spacing**: Wider gaps ($5.64) at lower levels, tighter ($1.88) near current price
- **Total pending buy orders**: 566.15 HYPE (~$52,652 notional)
- **Take-profit**: Reduce-only sell at **$93.409** for 10.75 HYPE (~0.44% above current price)

### Trading Mechanics
- **538 position cycles** over 112 days, averaging **5.5 hours per cycle**
- **Average cycle PnL**: $5.87
- **17.9 fills/day** on average (max 79 on volatile days, min 1 on quiet days)
- **Active 24/7** with peak activity during US hours (13:00–16:00 UTC)
- **Total closed PnL**: $3,463.26 | **Total fees**: $170.26 | **Net after fees**: $3,293.00
- **85 positive days / 27 negative days** — 76% win rate by day

### Strategy Logic
1. **Accumulate on dips**: Buy limit orders placed at progressively lower prices capture HYPE as it drops
2. **Scale out on rallies**: The reduce-only sell at $93.409 takes profit when price rises above entry
3. **Geometric sizing**: Larger positions at lower prices (more capital deployed on dips), smaller positions near current price (less risk)
4. **High-frequency scalping**: Short cycle durations (~5.5 hrs) capture small price movements ($0.35 avg spread between buy/sell prices)
5. **Cross-margin usage**: `userAdd` volume dominates `userCross` volume, indicating frequent margin additions to maintain positions

### Key Metrics
- **All-time PnL**: $5,188.22 (including unrealized)
- **Realized PnL**: $3,463.26 from 591 closed positions
- **Unrealized PnL**: ~$1,725 on open positions
- **Average daily PnL**: $30.92
- **Fee rate**: 0.045% cross / 0.015% add (standard tier)
