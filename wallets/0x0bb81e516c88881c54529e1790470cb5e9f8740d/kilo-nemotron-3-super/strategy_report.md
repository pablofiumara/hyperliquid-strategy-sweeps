# Strategy description for this wallet — kilo-nemotron-3-super

# source: final answer in output.txt

Based on analysis of 2000 perpetual futures trades for address 0x0bb81e516c88881c54529e1790470cb5e9f8740d on Hyperliquid, the derived trading strategies are:

## PRIMARY STRATEGY: LIQUIDATION-DRIVEN TRADING
- Monitors and trades during liquidation events of other users
- Executes trades to provide liquidation liquidity and benefit from cascades
- Evident from liquidation data embedded in trade history

## SECONDARY STRATEGIES:
1. **INTRADAY TREND FOLLOWING** (Strong long bias: 1405 opens vs 595 closes)
2. **SCALPING/MEAN REVERSION** (40% of trades followed by another within 1 hour)
3. **POSITION PYRAMIDING** (Builds positions via multiple consecutive opens, max 12 in a row)
4. **PROFIT TAKING/SCALING OUT** (Average close size 2.35x average open size)

## KEY CHARACTERISTICS:
- **Instrument**: Exclusively HYPE/USDC perpetual futures
- **Profitability**: ~3,428 USDC total PnL, average 0.53 HYPE per round-trip trade
- **Risk Management**: No liquidations of this address detected, consistent profit taking
- **Timeframe**: Median 9.8 minutes between trades (active intraday trading)
- **Edge**: Combines liquidation hunting with trend following and scalping

The trader appears sophisticated, disciplined, and consistently profitable by leveraging Hyperliquid's liquidation mechanism as a core trading edge.
