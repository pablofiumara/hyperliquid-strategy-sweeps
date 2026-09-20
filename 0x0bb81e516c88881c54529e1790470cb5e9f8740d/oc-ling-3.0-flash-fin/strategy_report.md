# Strategy description for this wallet — oc-ling-3.0-flash-fin

# source: final answer in output.txt

Open orders structure:
  6 limit BUY orders at descending prices (ladder/scale-in)
  1 reduce-only SELL order at 2.95 (profit target)

This is a SCALING IN / LADDER BUY strategy on HYPE perpetual
with systematic profit-taking on close.

Based on my analysis of the on-chain data for wallet `0x0bb81e516c88881c54529e1790470cb5e9f8740d`, here is the derived trading strategy:

---

## Trading Strategy: **Long-Only Ladder Scale-In on HYPE Perpetual**

### Core Profile
- **Asset**: Exclusively trades **HYPE/USDC perpetual** (no other coins)
- **Direction**: **100% LONG** — never opens short positions
- **Total realized PnL**: **~$3,594** across 637 closed trades
- **Win rate on closed trades**: **100%** (all 637 closes were profitable)

### Strategy Mechanics

1. **Ladder Buy / Scale-In**: The trader places **6 limit buy orders at descending prices** ($67.75 → $88.45), totaling ~555 HYPE in notional. This is a classic dollar-cost-averaging ladder to average down entry prices as the market dips.

2. **Systematic Profit-Taking**: Each cycle follows this pattern:
   - Open multiple long positions at different price levels
   - Close positions at a profit target (typically ~$4-5 PnL per cycle)
   - Repeat — 1363 open longs and 637 close longs across the history

3. **Current Open Orders** (live):
   - 6 buy orders at $67.75, $73.40, $79.04, $82.81, $86.57, $88.45 (scaling in)
   - 1 reduce-only sell order at $92.95 for 13.9 HYPE (profit target)

### Strategy Classification
- **Type**: Bullish trend-following with DCA averaging
- **Style**: Medium-frequency swing trading on HYPE perpetual
- **Leverage**: Uses cross-margin with significant position sizing
- **Key Trait**: Only goes long, accumulates on dips, takes profits on rallies

The trader is essentially running a **persistent bullish ladder strategy** on HYPE — systematically buying the dip across multiple price levels and taking profits when the price recovers, repeating continuously.
