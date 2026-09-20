# Strategy description for this wallet — kilo-step-3.7-flash

# source: final answer in output.txt

## Strategy Analysis: `0x0bb8…740d`

**Period:** 2026-05-22 → 2026-09-20 (~4 months)
**Asset:** HYPE only (pure single-asset perp strategy)
**Direction:** Long only (0 shorts)

---

### Core Strategy: Buy-the-Dip / DCA Accumulation in an Uptrend

| Metric | Value |
|---|---|
| Total fills | 2,000 |
| Reconstructed trades | 542 |
| Win rate | 100% (all 542 closed trades profitable) |
| Total realized PnL | **$3,428.49 USDC** |
| Total fees | $168.45 (4.9% of PnL) |
| Avg ROI per trade | **0.822%** |
| Avg hold time | **~5.3 hours** |
| Avg entries per trade | **2.58** |
| Total volume | $815,901 |

---

### Key Behavioral Patterns

**1. Heavy Scaling-In (DCA on Dips)**
- 59.4% of trades use multiple entries (322/542)
- 92.9% of multi-entry trades buy at progressively lower prices
- 27.0% pyramiding: increases position size on further dips
- Example: one trade opened with 2.75 HYPE @ $61.87, then added 1.38 @ $61.26, 1.38 @ $60.64, 2.48 @ $60.02, 2.48 @ $59.40, 8.80 @ $58.16, 16.50 @ $56.93, 30.25 @ $54.45 — averaging down to $56.54

**2. Tight Limit-Order Profit Taking**
- 588 of 595 closes used limit orders (99%); only 7 market closes
- Small, consistent gains per trade (ROI range: 0.006% – 4.071%)
- 30 partial closes (scale out of winning positions)

**3. Position Sizing**
- Ranges from 2.66 to 221.61 HYPE per trade (avg 11.26)
- Tends to size up during drawdowns (pyramiding)
- Most common size bucket: 5–10 HYPE (243 trades)

**4. Timing**
- No time-of-day bias — trades spread evenly across all 24 hours and all days of week
- Hold times: 248 trades <1h, 130 trades 1–3h, 78 trades 3–6h, 46 trades >12h
- Flexible duration: lets runners play out, doesn't force closes

**5. Fees**
- Extremely low fee ratio: 0.021% of volume
- 702 market opens, 703 limit opens (roughly 50/50)
- Fees represent only 4.9% of gross PnL — efficient execution

---

### Strategy Summary

This is a **long-only, dip-buying accumulator** on HYPE during a sustained bull trend (price: ~$55 → ~$95 over 4 months). The trader:

1. **Buys HYPE on pullbacks** — scales into longs as price drops (DCA/pyramiding)
2. **Takes profit on bounces** — closes via limit orders at small, consistent gains (~0.82% avg ROI)
3. **Never goes short** — pure bullish bias
4. **No visible stop-loss mechanism** — lets losing positions run (810 open fills with no corresponding close remain in the data; net current position: +9.74 HYPE)
5. **High-frequency, small-gain approach** — 542 closed trades over ~122 days ≈ ~4.4 trades/day

The 100% closed-trade win rate is notable but likely reflects a profit-taking discipline (only closing winners) rather than true flawless timing; unclosed losing positions may still be underwater. The strategy profits from HYPE’s overall uptrend by systematically buying weakness and selling strength.
