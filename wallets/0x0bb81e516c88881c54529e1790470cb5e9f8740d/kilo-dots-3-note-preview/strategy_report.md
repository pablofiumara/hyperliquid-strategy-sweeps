# Strategy description for this wallet — kilo-dots-3-note-preview

# source: final answer in output.txt

Based on the on-chain trade history (2,000 fills spanning 2026-05-22 to 2026-09-19), here's the derived strategy:

## Strategy: Grid/DCA Bot on HYPE Perpetual (Long-Only, 10x Leverage)

**Core mechanics:**
- **Long-only grid trader** on HYPE/USDC, using 10x cross margin
- Buys on price dips (grid levels stepping down ~0.5–0.6 USDC per fill), sells when price recovers to a higher grid level
- Position accumulates via multiple limit buys, then closes in full (or partial) chunks when price rises above the average entry

**Key metrics:**
- **Win rate: 100%** — 595/595 closed trades were profitable (0 losing closes)
- **Total closed PnL: ~3,426 USDC** over 120 days
- **Avg profit per close: ~5.76 USDC** (range: $0.04 – $107.59)
- **Total volume traded: 12,224 HYPE**
- **Grid step: ~0.5–0.6 USDC** between buy levels; sell triggers at ~0.5–1.5 USDC above last buy
- **227/1,999 trades executed with <1s gaps** — confirms automated bot execution

**Current state (as of latest API snapshot):**
- Holding **13.9 HYPE long** at entry $92.18, 10x cross leverage
- Account value: ~$4,237, unrealized PnL: −$7.73 on the open position
- Withdrawable: ~$57.65

**Risk profile:** Directional risk is mitigated by the grid structure (buying lower, selling higher), but the strategy is exposed to sustained downtrends if the grid is wide relative to capital — the current open position is underwater, showing the bot is actively averaging down.

In short: this is a **market-making/grid algorithm** that captures small price oscillations in HYPE by systematically buying dips and selling bounces, with a flawless realized win rate on closed trades.
