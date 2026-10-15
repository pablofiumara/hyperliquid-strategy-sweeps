# Strategy description for this wallet — kilo-dots-3-note-preview

## Strategy Derivation — `0xe755b71641b95ff7a6bd40030e9dc7ac7939e578`

### Summary

This is an **automated high-frequency grid/DCA trading bot** running on Hyperliquid. It trades **long-only** positions across 11 coins (NEAR, HYPE, XMR, ZRO, INJ, ONDO, JUP, UNI, ZEC, XLM, ETH) using a **geometric price grid with martingale position sizing** and a **profit-target sell** per grid level. It operates 24/7 with a US-hours bias, predominantly as a **maker** (74% limit orders).

### Evidence from on-chain data (2,000 fills, 2026-06-02 → 2026-09-26)

**1. Fully automated — cloid structure encodes the strategy**

Every fill has a `cloid` (client order ID). Decoding the bytes reveals 3 distinct order types from the same bot:
- `b1=0x01` (375 fills, 100% buys) — **base/initial buy** at a grid level
- `b1=0x02` (980 fills, 100% buys) — **ladder/add buy** at lower grid levels
- `b1=0x03` (404 fills, 100% sells) — **take-profit sell**

This is not a human; it's a programmatic grid engine.

**2. Grid mechanics (per cycle)**

Each cycle: the bot buys at descending price levels, then sells the accumulated position at a profit:
- **Grid step**: median ~0.5–1.5% per coin (NEAR 0.79%, ZRO 1.23%, JUP 0.88%, HYPE 0.56%, ONDO 0.58%, XMR 0.07%, ZEC 0.18%)
- **Profit target**: sell price is ~1.5–2.3% above the volume-weighted average buy price (e.g., ZRO: buy 1.153 → sell 1.171 = +1.56%; NEAR: avg buy 2.389 → sell 2.444 = +2.30%)
- **Martingale sizing**: buy size increases ~1.1–1.5x per lower grid level (e.g., ONDO: 29→35→42→53→65→88 units as price drops)
- **Win rate**: 98.2% across all sells (only 3 losing trades in 514 closes)

**3. Position & risk profile**
- **Cross-margin, 1x leverage** (no leverage used)
- **Long-only** — all 1483 buys are "Open Long", all 517 sells are "Close Long"
- **Maker bias**: 73.8% of fills are maker (limit orders), 26.2% taker
- **Base position sizes** per coin: NEAR ~12, ZRO ~10–13, JUP ~65–76, ONDO ~29–31, HYPE ~0.5–0.9, INJ ~4, UNI ~2.3, XMR ~0.06, ZEC ~0.03, XLM ~178

**4. Account trajectory**
- Implied starting equity: ~$1,413
- Current account value: $2,183 (with $74 in open unrealized losses)
- Net closed PnL in window: +$844 (after $24 in fees)
- Current open positions: INJ 29, UNI 13, ZRO 14.9, NEAR 77.8, ONDO 145, HYPE 3.51, XMR 0.351 (all underwater, consistent with grid accumulating during dips)

**5. Key behavioral signatures**
- 2,000 fills over 116 days = ~17 fills/day, but highly concentrated (e.g., 156 fills on 2026-09-03)
- Active hours: 00:00–23:00 UTC, peak at 15:00–16:00 UTC
- Multi-coin: up to 7 coins traded in a single day
- No TWAP orders, no large single fills (max notional ~$710, all HYPE sells)

### Conclusion

The strategy is a **market-making grid bot** that:
1. Places buy limit orders at geometric grid levels below market
2. Scales in (martingale) as price descends, increasing position size
3. Closes each grid cycle at a fixed ~1.5–2.5% profit target
4. Uses maker orders to minimize fees
5. Runs continuously across a basket of 11 mid-cap coins on Hyperliquid
