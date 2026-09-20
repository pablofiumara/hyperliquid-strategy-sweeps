# Strategy description for this wallet — kilo-laguna-s-2.1

# source: final answer in output.txt

## Strategy Derivation

**Trader**: `0x0bb81e516...` on Hyperliquid — exclusively trades **HYPE long** (no shorts, no other assets).

### Core Strategy: Scalping Bot with DCA Accumulation

**Entry (Taker Buy → Maker DCA)**
- Every cycle starts with a **market order (taker buy)** to enter a position
- Immediately follows with **limit orders (maker buys)** at progressively lower prices
- **92.9%** of multi-buy cycles show declining buy prices (buying the dip)
- Position sizes scale **~3.8x** at lower prices ($50–55 range avg 12.9 HYPE vs $90–95 avg 3.4 HYPE)

**Exit (Fixed Take-Profit)**
- Every position closed with a **maker sell (limit order)** at **~0.84% above the minimum buy price**
- **98.7%** of cycles (535/542) target this exact level
- **100% win rate** — never exits at a loss

**Execution Pattern** (most common → less common):

| Pattern | Count | % |
|---------|-------|---|
| T-M (1 taker buy, 1 maker sell) | 220 | 40.6% |
| TM-M (1 taker + 1 maker buy, 1 maker sell) | 76 | 14.0% |
| TT-M (2 taker buys, 1 maker sell) | 47 | 8.7% |
| TMM-M | 34 | 6.3% |
| TMMMM-M | 29 | 5.4% |

**Performance**
- 542 completed cycles over 120 days
- **$3,428 realized P&L** (avg ~$5.77/cycle, ~$38/day)
- Avg cycle duration: **5.3 hours** (median 1.2h)
- Total fees: $168.45 (0.49% of notional — benefiting from maker rebates)
- Currently holding 13.90 HYPE (open position)

**Summary**: This is an automated scalping bot that **enters with a market order, accumulates via limit orders on price dips (DCA), and exits at a fixed ~0.84% profit target** — always selling via maker limit orders. The 100% win rate and rigid profit-taking level indicate algorithmic execution with strict risk controls. It is long-only on HYPE, does not use stop-losses, and avoids overnight risk (median holding time 1.2 hours).
