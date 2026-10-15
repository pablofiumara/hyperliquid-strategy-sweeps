# Strategy description for this wallet — oc-ling-3.0-flash-fin

Based on all the on-chain data I've collected and analyzed independently, here is the derived trading strategy:

---

## Strategy: **Long-Only Grid DCA Accumulation**

### Core Approach
The trader operates a **long-only grid trading / dollar-cost averaging (DCA) system** across 11 altcoins, never shorting. All positions use **cross margin at 1x leverage** (spot-like exposure with no amplification).

### Grid Architecture (Per Coin)
For each coin, the trader places:
- **Multiple limit BUY orders** at descending price levels (the grid)
- **A single limit SELL order** above the current price (profit target)
- All orders are **GTC (Good-Till-Cancelled) limit orders** — never market orders

Current open order grid (confirmed from API):
| Coin | Buy Levels | Sell Level | Sell Premium |
|------|-----------|------------|-------------|
| ZRO | $1.47, $1.53, $1.58, $1.62 | $1.70 | +10.2% |
| HYPE | $77.84, $86.75 | $96.56 | +25.7% |
| INJ | $6.55, $7.43 | $8.49 | +8.2% |
| NEAR | $3.93, $4.42 | $5.12 | +31.8% |
| ONDO | $0.43, $0.49, $0.53 | $0.57 | +28.9% |
| UNI | $8.48 | $10.64 | +25.5% |
| XMR | $503.82 | $611.83 | +21.4% |

### Key Metrics
- **2000 fills** over 116 days (Jun 2 – Sep 26, 2026)
- **77 active trading days** (66% of the time)
- **26 trades/day average**, peaking at 159 (Sep 3)
- **99.4% win rate** on closed trades (514 profitable, 3 losing)
- **Total closed PnL: $868.72** | Fees: $24.40 | **Net: $844.32**
- **Cum funding received: ~$23.01** (HYPE: $11.40, XMR: $7.65, NEAR: $2.14)
- **Account value: $2,181.70** | All 7 open positions are LONG

### Top Performers by PnL
| Coin | Fills | PnL | Buy% |
|------|-------|-----|------|
| HYPE | 373 | $340.80 | 69.4% |
| XMR | 505 | $105.40 | 79.8% |
| NEAR | 295 | $216.29 | 74.2% |
| INJ | 159 | $55.66 | 71.7% |
| ZRO | 158 | $36.91 | 65.8% |
| ONDO | 154 | $39.80 | 73.4% |

### Behavioral Characteristics
1. **Trend acceleration**: 73% of all fills occurred in September 2026, with trading volume scaling from ~53 fills in July to ~1,469 in September
2. **Partial profit-taking**: sells represent ~26% of total fills — the trader takes small profits while accumulating the majority of the position
3. **Mean-reversion within grid**: average sell price is only 0.18–2.5% above average buy price per coin, capturing small price oscillations
4. **Long-term conviction**: despite 1x leverage and partial profit-taking, the trader maintains large net long exposure across all 7 held coins
5. **Funding income**: collects positive funding on HYPE and XMR (negative funding rates = shorts pay longs), adding to returns
6. **No stop losses**: no position TPSL or trigger orders detected — positions are managed purely through limit orders

### Summary
This is a **patient, systematic grid DCA long accumulation bot** that places layered limit buy orders below the market and a single limit sell above, repeatedly capturing small mean-reversion profits (~0.2–2.5% per cycle) while continuously accumulating coin exposure. The 99.4% win rate and consistent positive funding income suggest the strategy is well-calibrated to each coin's volatility profile.
