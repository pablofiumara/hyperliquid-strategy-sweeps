# Strategy description for this wallet — kilo-laguna-s-2.1

1. DCA (Dollar-Cost Averaging) entry with maker limit orders
2. Profit-target exits via maker limit orders at coin-specific thresholds
3. Long-only perpetual trading
4. Taker for initial entry, maker for DCA additions and exits
5. HYPE exception: more active taker trading, no cloid encoding
6. Systematic position sizing: equal dollar amounts per DCA layer (~1/r scaling)

## Trading Strategy Analysis: `0xe755b71641b95ff7a6bd40030e9dc7ac7939e578`

### Overview
- **Data period**: March 4 – September 26, 2026 (6.5 months)
- **Total fills**: 2,234 (2,195 perp + 39 spot HYPE)
- **Direction**: Long-only (1,598 buys, 597 sells; 2 short trades)
- **Total realized PnL**: $1,021.77 | Fees: $29.28 | Funding paid: $25.50
- **Net profit**: ~$967 (1.5% return on $66,117 buy volume)
- **Win rate**: 99.5% (592 wins, 3 losses)

---

### Core Strategy: Systematic DCA with Profit-Targeted Maker Exits

#### 1. Entry Phase — DCA with Taker + Maker Layers
The trader uses a **three-layer DCA system** encoded in Client Order IDs (cloids):

| CloID Prefix | Role | Side | Order Type |
|---|---|---|---|
| `0x010101a0...` | **Layer 1** – Initial entry | Always Buy | Taker (market) |
| `0x010201a0...` | **Layer 2-N** – DCA additions | Always Buy | Maker (limit) |
| `0x010301a0...` | Exits | Always Sell | Maker (limit) |
| *(no cloid)* | HYPE-specific trading | Mixed | Mixed maker/taker |

**Key pattern across all coins**:
- **Initial entry** is a **taker (market) buy** at current price
- **Subsequent additions** are **maker (limit) buy orders** placed *below* market as price declines
- **Size increases** proportionally to price decline (~1/r scaling: buy more as price drops)
- Example (XMR): buys at 444.93 → 444.64 → 444.80 → 444.88 → 444.33 with sizes 0.076 → 0.088 → 0.083 → 0.079 → 0.092

#### 2. Exit Phase — Maker Limit Sells at Coin-Specific Profit Targets
Every sell (A-side fill) closes the **entire remaining position** (startPosition/sz ratio = 1.00 for all coins). Profits are captured via **maker limit orders** at consistent per-coin target returns:

| Coin | Median Return | Precision | Exit Method |
|---|---|---|---|
| XMR | 0.70% | 98% within 0.75% of median | Maker (limit) |
| ZEC | 0.60% | 97% within 0.75% | Maker (limit) |
| INJ | 1.50% | 100% within 0.75% | Maker (limit) |
| ZRO | 1.50% | 96% within 0.75% | Maker (limit) |
| NEAR | 2.00% | 100% within 0.75% | Maker (limit) |
| ONDO | 2.10% | 100% within 0.75% | Maker (limit) |
| HYPE | 1.75% | 76% within 0.75% | **Taker (market)** |

#### 3. HYPE Deviation — High-Frequency Taker Trading
HYPE (38.8% of capital, 25.4% of fills) deviates from the systematic pattern:
- **No cloid encoding** (422/568 fills have no cloid)
- **Mixed maker/taker** (42% taker, vs ~28% for other coins)
- **83% of exits are taker (market sells)** — aggressive exit style
- Uses the taker-maker mix for both entry and exit, unlike the systematic maker-pattern on other coins
- This appears to be a higher-conviction, more reactive approach to HYPE specifically

#### 4. Position Sizing & Capital Allocation
- **Per-position entry**: ~$50–$200 depending on coin
- **DCA layers**: 2–6 average per position (max 15 for HYPE)
- **Coin allocation** (total buy USD):
  - HYPE: $25,663 (38.8%)
  - XMR: $13,899 (21.0%)
  - NEAR: $10,926 (16.5%)
  - ZEC: $4,205 (6.4%)
  - INJ: $3,929 (5.9%)
  - ZRO: $2,448 (3.7%)
  - ONDO: $1,902 (2.9%)

#### 5. Timing & Activity Patterns
- **Activity peaks**: 15:00–16:00 UTC (7.4% of trades) — US/European market hours
- **Most active days**: Thursday (18.5%), Wednesday (16.9%), Friday (16.9%)
- **Average position duration**: 13.1 hours (median 1.5 hours)
- **Funding payments**: Every 8h, 1,469 records. Paid net -$25.50 USDC (funding rates were positive, longs pay shorts)

#### 6. Risk Management
- **99.5% win rate**: 592 profitable exits, 3 losses
- **All 3 losses** were **taker (market) sells** during volatile moves:
  - HYPE: -$8.20 (July 17, market sell at 60.706)
  - ZEC: -$2.21 (Sept 4, market sell at 1018.90 after extended DCA session)
  - HYPE: -$1.25 (Sept 4, market sell at 85.195)
- **No stop-losses** visible — exits rely on maker limit orders at profit targets
- Taker exits used as fallback when maker orders don't fill and price moves adversely

---

### Conclusion: The Strategy in One Sentence

The trader systematically builds **long-only positions** using **DCA with equal-dollar scaling** (taker entry → maker limit additions as price drops), then exits the **full position at coin-specific profit targets** (0.5–2% returns) using **maker limit orders** — with **HYPE as a higher-conviction exception** trading more aggressively via taker orders.
