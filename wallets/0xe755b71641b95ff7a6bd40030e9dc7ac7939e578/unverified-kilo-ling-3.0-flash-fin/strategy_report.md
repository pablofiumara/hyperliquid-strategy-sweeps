# Strategy description for this wallet — unverified-kilo-ling-3.0-flash-fin

Based on my independent analysis of 2000 fills and 1710 historical orders from the Hyperliquid API, here is the derived trading strategy:

---

## Trading Strategy: Systematic Limit-Order Laddering DCA Long

### Core Approach
**100% long-only directional trading** across 11 altcoins using a **limit-order laddering / dollar-cost-averaging (DCA) strategy** with quick profit-taking.

### Key Metrics
| Metric | Value |
|--------|-------|
| Total fills analyzed | 2,000 |
| Closed positions | 517 |
| Realized PnL | **$868.72** |
| Avg PnL per closed trade | **$1.68** |
| Win rate (closed positions) | **99.4%** (514/517) |
| Total fees paid | $24.40 |
| Current open notional | ~$18,157 |
| All-time account value | ~$2,193 |

### Entry Strategy: Limit Order Laddering
- **Order type**: All Limit orders (1,710 total)
- **TIF**: 1,542 GTC (Good Till Canceled) + 168 IOC (Immediate or Cancel)
- **Method**: Places multiple limit buy orders at progressively lower price levels (laddering). For example, ZRO currently has open limit buys at $1.11, $1.114, $1.127, $1.131, $1.134, $1.137, $1.149, $1.152 — creating a price ladder.
- **Scaling in**: Average 2–6 separate open fills before each close event. XMR averages 6 opens per close cycle.
- **All orders use `cloid`** (conditional order IDs) for tracking and management.

### Exit Strategy: Reduce-Only Limit Orders
- **503 active reduce-only close orders** currently placed
- Closes positions via reduce-only limit sell orders at target prices above entry
- **Short hold times**: Average 1.9 hours (ZRO), 4.7 hours (NEAR), 10.5 hours (XMR), 51.9 hours (HYPE)
- Quick profit-taking — positions are closed as soon as price reaches target

### Coin Distribution (by fill count)
| Coin | Opens | Closes | Realized PnL | Notional Vol | Avg Hold |
|------|-------|--------|-------------|-------------|----------|
| XMR | 403 | 102 | $105.40 | $27,690 | 10.5h |
| HYPE | 259 | 114 | $340.80 | $35,683 | 51.9h |
| NEAR | 219 | 76 | $216.29 | $21,677 | 4.7h |
| ZEC | 145 | 40 | $21.78 | $8,431 | — |
| INJ | 114 | 45 | $55.66 | $7,670 | — |
| ZRO | 104 | 54 | $36.91 | $4,908 | 1.9h |
| ONDO | 113 | 41 | $39.80 | $3,763 | — |
| JUP | 56 | 22 | $19.52 | $2,749 | — |
| UNI | 48 | 16 | $21.88 | $2,121 | — |
| XLM | 17 | 6 | $10.28 | $1,200 | — |
| ETH | 5 | 1 | $0.40 | $135 | — |

### Notable Characteristics
- **No TWAP orders** — all manual limit order placement
- **No trigger/stop orders** — no position TPSL or conditional triggers
- **Margin constraints**: 6 `perpMarginRejected` orders (tried to open larger positions than margin allowed)
- **4 `reduceOnlyRejected`** orders (attempted to close more than position size)
- **24/7 activity** across all time zones, accelerating in September 2026
- **Most active recently**: ZRO (158 fills in last 5 days), NEAR (138)
- **IOC orders** (168) likely used for immediate partial fills or testing liquidity

### Strategy Summary
The trader systematically **ladder-loads limit buy orders** across multiple altcoins at different price levels, gradually accumulating long positions as the market moves. When positions become profitable, they **quickly close with reduce-only limit orders** at target prices. The 99.4% win rate on closed positions suggests tight profit targets and disciplined exits. The strategy is essentially a **high-frequency, multi-coin, systematic DCA long with quick profit-taking** — not a swing trade or hold strategy.
