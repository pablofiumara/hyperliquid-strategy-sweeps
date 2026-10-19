# Strategy description for this wallet — kilo-nemotron-3-super

Based on analysis of the trader's on-chain fills (most recent 2000 fills spanning ~116 days), the trading strategy is characterized as follows:

- **Direction**: Exclusively long positions (no shorts detected). All fills are either "Open Long" (buys) or "Close Long" (sells).
- **Trade Frequency**: High activity—hundreds of trades per coin over the period (e.g., ~2.8 trades/day for HYPE, ~2.2/day for NEAR, ~4.1/day for XMR).
- **Holding Period**: Positions held for several hours to a couple of days on average:
  - HYPE: ~49.7 hours (2.1 days)
  - NEAR: ~8.6 hours
  - XMR: ~13.5 hours
  - ZRO: ~3.5 hours
  - Other coins range between ~3.5–12 hours.
- **Profitability**: Consistently profitable round trips (buy low, sell high). Profit per unit size varies by coin (e.g., HYPE: ~1.43 USDC/unit, XLM: ~0.0034 USDC/unit), but all coins show positive average sell-buy price differentials.
- **Time Distribution**: Trades are fairly uniform across hours of the day (UTC), indicating no strong time-of-day bias.
- **Asset Scope**: Diversified across multiple cryptocurrencies (ZRO, NEAR, ONDO, INJ, HYPE, XMR, ZEC, JUP, ETH, UNI, XLM, etc.), suggesting a systematic, multi-asset approach.

**Strategy Summary**: The trader employs a long-only, medium-frequency strategy that enters positions after identifying buying opportunities and exits after short-term price appreciation (typically hours to days). The approach appears rules-based and systematic, profiting from short-term momentum or mean-reversion across a diversified crypto portfolio, with trades distributed evenly throughout the day. No evidence of shorts, leverage, or complex derivatives is observed in the fill data.
