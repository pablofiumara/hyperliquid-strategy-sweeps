# Strategy description for this wallet — kilo-nemotron-3-ultra

# source: final answer in output.txt

Based on my analysis of the full trade history (386 cycles, ~3,400 trades) for address `0x0bb81e516c88881c54529e1790470cb5e9f8740d`, here's the derived trading strategy:

## **Strategy: HYPE Perpetual Grid/Accumulation with Residual Short Hedge**

### **Core Pattern**
- **Single asset**: Exclusively trades **HYPE** (Hyperliquid native token) perpetuals
- **Directional bias**: **Net long** with a consistent **~4.16 HYPE residual short** position maintained after each cycle
- **Cycle structure**: Build large long position (10-130+ HYPE) → Close most → Leave ~4.16 short → Immediately rebuild long

### **Key Mechanics**

| Aspect | Details |
|--------|---------|
| **Position sizing** | Scales from ~4 HYPE (small cycles) to 100+ HYPE (large cycles) |
| **Entry style** | **Maker orders** (mostly `crossed: false`) - posts limit orders, earns maker rebates |
| **Exit style** | Mix of maker/taker, closes in chunks |
| **Avg hold time** | Minutes to days (small cycles: 5-30 min; large cycles: hours to days) |
| **Profit target** | Consistently **~$0.50-0.80/HYPE spread** (entry vs exit) |
| **Residual short** | **Exactly ~4.16 HYPE** maintained after every close - appears intentional |

### **PnL Profile**
- **Total realized PnL**: **$3,428** (from ~3,400 trades)
- **Total fees**: **$168** (net **+$3,260** after fees)
- **Win rate**: Near 100% on closed cycles (every cycle shows positive PnL)
- **Risk**: Carries large directional exposure during build-up (up to 130+ HYPE ≈ $10k+ notional)

### **Strategy Classification**
This is a **market-making / inventory management strategy** with a twist:
1. **Accumulates long inventory** via maker limit orders (earning spread + rebates)
2. **Distributes inventory** by closing at slightly higher prices
3. **Maintains a permanent ~4.16 HYPE short hedge** - likely for:
   - Funding rate arbitrage (collecting funding on short while long)
   - Delta-neutral positioning against spot holdings
   - Maker rebate optimization on both sides

### **Evidence of Automation**
- Sub-second trade sequences (multiple orders at same timestamp)
- Precise 4.16 HYPE residual every cycle
- 24/7 operation across months
- Consistent ~$0.50-0.80 spread capture regardless of price level ($55-$94 range)

### **Risk Factors**
- **Large drawdown risk** during accumulation phases (position grows 10-30x residual)
- **Funding rate exposure** on large longs
- **Single-asset concentration** (100% HYPE)
- **Smart contract / oracle risk** on Hyperliquid

This appears to be a **professional market-making bot** optimized for Hyperliquid's maker rebate structure and HYPE's funding rate dynamics.
