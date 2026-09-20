# Strategy description for this wallet — oc-big-pickle

# source: final answer in output.txt

## Strategy derivation for `0x0bb8…740d`

This is a **single-coin, long-only, mean-reversion grid/DCA bot on HYPE perps** — essentially a "buy the dip, sell at a fixed take-profit" machine. Evidence from Hyperliquid's API (2,000 most-recent fills, funding, portfolio, fees, open orders):

**The trade cycle (594 completed cycles in ~4 months ≈ 5/day):**
1. **Open** — market (taker) buy, always (541/541 cycles via a crossed order).
2. **Build** — if price dips, average down with limit buy adds (~1-2 per cycle, up to 11). Adds are 81% limit orders (698/857).
3. **Exit** — close the *entire* position with a single reduce-only limit (maker) sell at a fixed **~+0.8–0.9% take-profit** above average entry (99% of exits, 535/541). Median realized return 0.84%, median hold ~1.2h.
4. Repeat.

**Live config on the account right now** makes the mechanism explicit:
- One reduce-only TP sell: `92.95` vs entry `92.1758` → **+0.84%** target.
- A **geometric buy ladder**: `88.45 / 86.57 / 82.81 / 79.04 / 73.40 / 67.75` with **gaps widening 2.1% → 7.7%** and **sizes roughly doubling** per rung (`11.7 → 21.9 → 40.3 → 75 → 141 → 265` ≈ **$40.5k resting bids** vs ~$4.2k perp equity).

**Risk/edge profile:**
- **Never closes at a loss** in the whole sample: 0 negative `closedPnl` out of 595 closes. It babels drawdowns, adding size until price recovers to TP — a Martingale-ish tail-risk structure, not stop-loss disciplined (undercapitalized bag right now: 13.9 HYPE long, −$16 uPnL).
- Typical position is tiny: median cycle notional ~$350 (0.08–0.1x), mean $748, rare large cycles up to $12.8k.
- Fee/funding drag is small: ~0.05% round-trip cost (taker open + maker close), net funding paid only −$97 all-time.
- Bonus: resting bids get filled on *other traders' liquidation dumps* (8 fills tagged `liquidation`).
- 24/7 automated behavior, slightly denser 13–16 UTC.

**Performance:** cumulative perp PnL all-time ≈ **+$5,050** on ~$8k total capital (≈$4.2k perp + $3.9k spot USDC), growing steadily ~$500–700/month. Net of fees the last 2,000 fills alone show ≈ +$3,260.

**Verdict:** a HYPE-only dip-buying grid bot that DCA-averages down with an exponentially-sized ladder, always exits on a ~0.9% limit take-profit, and historically never realises a loss — trading small, patient edge with a hidden multi-x crash-risk tail.
