# Trader Strategy Derivation — `0x0bb8…740d` (hyperx.trade / Hyperliquid)

**Address:** `0x0bb81e516c88881c54529e1790470cb5e9f8740d`
**Venue:** Hyperliquid perps (account shown on the hyperx.trade trader page)
**Data window:** 2025-10-13 → 2026-09-20 (341 days, 4 876 fills)
**Method:** full trade/order/ledger history pulled from the Hyperliquid public info API
(`userFillsByTime`, `historicalOrders`, `userNonFundingLedgerUpdates`, `fundingHistory`,
`clearinghouseState`, `frontendOpenOrders`, `candleSnapshot`) and reconstructed mechanically.

---

## TL;DR — one strategy, run as a bot

This is a **single-asset, long-only mean-reversion "buy-the-dip" ladder (grid/DCA-martingale)
bot on HYPE** that:

1. after every completed round trip, immediately **re-enters long** with a marketable
   order of **2 base units** at *anchor +1 %* (taker);
2. rests a **10-rung buy ladder below the anchor** at **−1 %, −2 %, −3 %, −4 %, −6 %, −8 %,
   −12 %, −16 %, −22 %, −28 %**, with coin sizes scaling **1, 1, 1.8, 1.8, 6.4, 12, 22, 41,
   77, 145 × unit**;
3. exits the **entire position** with a reduce-only limit sell at
   **volume-weighted average entry × 1.0084** (+0.84 %), cancelled/re-placed after every fill;
4. has **no stop-loss** — it holds the ladder inventory until price recovers +0.84 % above
   VWAP (median hold 1.1 h, max observed 8.4 days);
5. sizes the unit at **≈2 % of account equity**, re-scaled in steps as equity changes.

Result over 11 months: **1 347 round trips, 1 344 wins / 2 losses (99.9 % win rate)**,
+5 458 USD gross realized PnL, +5 093 USD net of fees/funding, on 3 007 USD net deposits
(≈106 % profit; owner withdrew ≈13 000 USD along the way). The only losses were two
market exits made to free cash for withdrawals (2025-12-25, −4.50 USD; 2026-03-10, −3.11 USD).

No other asset, no shorts, no other strategy was found. (Only three non-ladder actions exist:
those two manual/forced exits, and take-profit limits that fill *as taker* when price gaps up.)

---

## 1. Account at a glance

| metric | value |
|---|---|
| coins traded | **HYPE only** (4 876/4 876 fills) |
| direction | **Open Long 3 433 / Close Long 1 443** (never short) |
| total volume | 1 303 903 USD |
| fees | 268 USD (maker 0.0144 %, taker 0.0432 % effective) |
| funding | −96.95 USD |
| gross realized PnL (`closedPnl`) | **+5 458 USD** |
| net of fees + funding | **+5 092.8 USD** |
| maker / taker share of notional | 78.5 % / 21.5 % |
| margin mode | cross, max 10×, long-only |
| sessions | 257 active days of 341; only long stop is 2025-12-25 → 2026-02-05 (42 days, capital pulled) |
