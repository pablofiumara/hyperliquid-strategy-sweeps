# Strategy description for this wallet — cline-laguna-s-2.1

(salvaged from output.txt analysis blocks; model used submit_and_exit so no work/*.md was written)

1. **Position sizing**:
   - Sell sizes are consistently LARGER than buy sizes. For example:
     - HYPE: buy avg=0.936, sell avg=2.104 (sells are 2.24x larger)
     - INJ: buy avg=4.42, sell avg=10.55 (sells are 2.39x larger)
     - NEAR: buy avg=12.68, sell avg=35.50 (sells are 2.8x larger)
     - XMR: buy avg=0.069, sell avg=0.269 (sells are 3.9x larger)
     - ONDO: buy avg=38.81, sell avg=103.41 (sells are 2.66x larger)
     - UNI: buy avg=2.46, sell avg=6.56 (sells are 2.67x larger)
   - This is very interesting! The trader makes many small buys (dollar-cost averaging or scaling in) and then makes larger sells (taking profits). This is NOT a swing trading strategy where you buy a position and hold it. Instead, it appears to be:
     - Many small buys to build up a position
     - Fewer, larger sells to realize profits

**PROFIT TARGETS PER COIN (VERY SYSTEMATIC!):**
- ETH: 0.59% (1 cycle)
- HYPE: avg 1.81%, median 1.71%, most common 1.7% (37.8% of cycles hit this)
- INJ: avg 1.51%, and 31 out of 32 cycles hit EXACTLY 1.5%! This is a fixed 1.5% target!
- JUP: avg 1.53%, most common 1.6% (8 out of 16 cycles)
- NEAR: avg 2.08%, median 2.00%, 37 out of 63 cycles hit EXACTLY 2.0%! Fixed 2.0% target!
- ONDO: avg 2.16%, median 2.10%, 29 out of 34 cycles hit EXACTLY 2.1%! Fixed 2.1% target!
- UNI: avg 2.23%, median 2.10%, 8 hit 2.1% and 6 hit 2.4%
- XLM: avg 1.64%, 3 hit 1.9%
- XMR: avg 0.80%, median 0.70%, 47 out of 56 cycles hit EXACTLY 0.7%! Fixed 0.7% target!
- ZEC: avg 0.56%, median 0.60%, 38 out of 39 cycles hit EXACTLY 0.6%! Fixed 0.6% target!
- ZRO: avg 1.54%, median 1.50%, 45 out of 47 cycles hit EXACTLY 1.5%! Fixed 1.5% target!

| Coin | Price (Sep) | Fixed Target | Cycles Hit Exactly | StdDev |
|------|------------|-------------|-------------------|--------|
| **XMR** | ~$500 | **0.70%** | 47/56 (84%) | 0.27% |
| **ZEC** | ~$900 | **0.60%** | 38/39 (97%) | 0.27% |
| **ETH** | ~$2,485 | **0.59%** | 1/1 (100%) | 0.00% |
| **INJ** | ~$7.8 | **1.50%** | 31/32 (97%) | 0.06% |
| **ZRO** | ~$1.46 | **1.50%** | 45/47 (96%) | 0.20% |
| **JUP** | ~$0.26 | **1.60%** | 8/16 (50%) | 0.16% |
| **HYPE** | ~$73 | ~1.70% | 14/74 (19%) | 0.63% |
| **XLM** | ~$0.19 | **1.90%** | 3/5 (60%) | 0.52% |
| **NEAR** | ~$3.9 | **2.00%** | 37/63 (59%) | 0.13% |
| **ONDO** | ~$0.44 | **2.10%** | 29/34 (85%) | 0.17% |
| **UNI** | ~$9.5 | **2.10%** | 8/14 (57%) | 0.15% |

3. **Exit Mechanism**:
   - Single sell order closes the full accumulated position (77.5% of cycles)
   - **Fixed per-coin profit targets**:
     - XMR: 0.7% (47/56 cycles hit exactly)
     - ZEC: 0.6% (38/39 cycles hit exactly)
     - ETH: 0.59% (1/1 cycle)
     - INJ: 1.5% (31/32 cycles hit exactly)
     - ZRO: 1.5% (45/47 cycles hit exactly)
     - JUP: 1.6% (8/16 cycles)
     - HYPE: ~1.7% (14/74 cycles, more variation)
     - XLM: 1.9% (3/5 cycles)
     - NEAR: 2.0% (37/63 cycles hit exactly)
     - ONDO: 2.1% (29/34 cycles hit exactly)
     - UNI: 2.1% (8/14 cycles)
   - 82% maker orders for sells, 18% taker (passive exit)

4. **Position sizing**:
   - The sell-buy ratio is mostly < 1.0 (sells are slightly smaller than buys), meaning the bot usually closes the full position and sometimes carries a small remainder
   - Wait, that's interesting. The "Sell/Buy ratio: avg=0.957" for HYPE means sells are slightly smaller than buys. This could indicate partial closes (the bot closes most of the position but leaves a small amount).
   - The buy sizes are relatively consistent within cycles (low CV), especially for UNI (0.079), INE (0.099), XMR (0.160), JUP (0.172), NEAR (0.162), ZEC (0.196), ONDO (0.218), ZRO (0.220)

The strategy characteristics:
- **Entry**: Dollar-cost averaging with small incremental buys, possibly at slight price dips or on volume
- **Exit**: Profit-taking at a small target (likely 1-2% gain, based on the exit price being ~1.4% above entry on average)
- **Risk management**: 99.7% win rate, but only 0.1% loss rate. This suggests the bot might be using a stop-loss or simply not closing losing positions (but 1 loss on 388 cycles = 0.26%)
- **Position sizing**: Larger positions for coins with more fills (HYPE 2.99 avg, XMR 0.42 avg, INJ 13.96 avg, NEAR 40.88 avg, ONDO 117.78 avg)

2. **Coins traded (11 coins)**:
   - HYPE: 373 fills (most active), $35,684 volume, $340.80 PnL (most profitable)
   - XMR: 505 fills, $27,691 volume, $105.40 PnL
   - NEAR: 295 fills, $21,677 volume, $216.29 PnL
   - INJ: 159 fills, $7,670 volume, $55.66 PnL
   - ZEC: 185 fills, $8,431 volume, $21.78 PnL
   - ZRO: 158 fills, $4,909 volume, $36.91 PnL
   - ONDO: 154 fills, $3,764 volume, $39.80 PnL
   - JUP: 78 fills, $2,749 volume, $19.52 PnL
   - UNI: 64 fills, $2,122 volume, $21.88 PnL
   - XLM: 23 fills, $1,201 volume, $10.28 PnL
   - ETH: 6 fills, $135 volume, $0.40 PnL

3. **Buy-sell size ratio**: Sells are consistently 2-5x larger than buys on average. This confirms the **scaling out** pattern. But interestingly, the NET position for each coin is very small or zero:
   - ETH: net=0.0000 (fully flat)
   - HYPE: net=2.55 (small long remaining)
   - INJ: net=29.0 (current position)
   - NEAR: net=77.8 (current position)
   - ONDO: net=145.0 (current position)
   - UNI: net=13.0 (current position)
   - XMR: net=0.351 (small long remaining)
   - ZRO: net=14.9 (current position)
   - JUP, XLM, ZEC: net=0.0000 (fully flat)
