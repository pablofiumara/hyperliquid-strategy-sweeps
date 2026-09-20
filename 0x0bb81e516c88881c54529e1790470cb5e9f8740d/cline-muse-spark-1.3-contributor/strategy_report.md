# Strategy: 0x0bb81e516c88881c54529e1790470cb5e9f8740d (hyperx.trade/Hyperliquid)

Address: 0x0bb81e516c88881c54529e1790470cb5e9f8740d
Window: 2025-10-13 -> 2026-09-20. Sources: Hyperliquid info API
(userFillsByTime paginated 4876 fills, clearinghouseState,
spotClearinghouseState, openOrders, historicalOrders 1282,
userFunding 485, userNonFundingLedgerUpdates, userFees, portfolio).

## 1. Summary - ONE strategy

Single-market, long-only, grid / martingale mean-reversion maker on
HYPE-PERP only. There are not multiple strategies.

Loop, repeated flat-to-flat (1346 cycles reconstructed):

1. Open small LONG with taker buy (first buy crossed=True 99.93%).
2. Layer resting maker bids below at ~-1.0% steps with martingale
   size scaling (0.5x/1.0x/1.8x/3.6x modes, up to 12 levels).
3. Exit whole position with one resting reduce-only maker sell at
   ~+0.84% above average entry. Sells crossed=False 98.7%.
4. Repeat. Never short, no triggers/TWAP/stops, no other coin, no spot.

Fingerprint table:

- Coins: HYPE 4876/4876 = 100%.
- Dirs: Open Long 3433 / Close Long 1443, zero shorts.
- Cycles flat-to-flat via startPosition+sz: 1346, leftover 13.9 = live pos.
- Fee realised: taker ~0.0432% vs maker ~0.0144%.
- Markup sell vs avg buy: median +0.84%, mean +0.85% (same for 1-buy
  and multi-buy cycles).
- Grid step: median -1.014% (1248/1597 steps round to -1.0%).
- Fills/cycle median 3 mean 3.62 max 17. Hold median 1.07h mean 5.05h.
- Win rate 1344/1346 = 99.85% (bag-hold, not stop-loss).
- closedPnl +5458.12 / fees 268.43 / net +5189.70; funding -96.95.
- Avg/cycle +$4.06 (median $2.49); ~$27.43/day over 199 active days.
- Max long ever 280.78 HYPE (2025-12-07 dip).
- Leverage cross 10x set but margin used ~$127 on $1273 notional.
## 2. Exact mechanics

### 2.1 Entry - starter long (taker)

- Small limit that crosses spread (crossed=True), effectively market buy.
- Starter notionals grew with equity: ~$80 (Oct25) -> ~$90-150
  (Feb-Apr26) -> ~$270-340 (Jun-Sep26). Sep26 median ~$336 (~3.5 HYPE).
- After fill bot posts (a) reduce-only TP sell for full size at
  entry*~1.0084 and (b) maker buy ladder below.
- Simple scalp ex (2025-10-13): B 2.02 @42.314 taker -> A 2.02 @42.67
  maker = +0.84%, +$0.72.

### 2.2 Grid - averaging-down ladder (maker)

- Each level separate oid, Gtc limit, reduceOnly=false, filled on dips.
- Spacing: overwhelmingly -1.0%/level (median -1.014%). Deep safety
  levels sometimes -2.1%/-4.3% (144/7 cases) to stretch in crashes.
- Sizing martingale-ish capped: pattern ~1/0.5/0.5/1/1/2/4/8x starter.
  Measured multipliers modes 0.5x(626) 1.0x(569) 1.8x(255) 3.6x(88).
- Depth buy-count over 1346 cycles: 1:573 2:286 3:172 4:94 5:87 6:50
  7:44 8:24 9-12:15. So 42.6% are 1-buy scalps, 57.4% average down.
- On each new buy fill TP is cancelled/replaced to cover new VWAP
  (seen in historicalOrders chained A-RO cancels 94.916->94.591->
  94.191->93.525).

Large ex (2026-07-27->07-30, 12 buys/2 sells, +$63.04):
60.074x5.7 ->59.485x2.85 ->58.884x2.85 ->58.283x5.13 ->57.683x5.13
->56.481x18.24 ->55.279x34.2 ->52.876x62.7 then SELL 136.8 @55.364.

### 2.3 Exit - fixed-markup TP (maker)

- One price full size (sell-count=1 in 1280/1346 cycles). Rare 2-8
  sells are partial fills of one oid (319 oids multi-fill, 1.11 avg).
- Limit = VWAP(buys)*~1.0084. 559 pure 1-buy cycles median 0.84%
  (510 at 0.8%, 43 at 0.9%, range 0.59-2.67%); 773 multi-buy median
  0.84% too. No trailing/scale-out.
- Maker (crossed=False), 0.015% add rate (realised 0.0144% after 4%
  referral discount). Holds: 1-buy median 0.29h (mean 0.66h p90 1.69h);
  multi median 2.76h (mean 8.3h max 200.65h).

### 2.4 Crash behaviour - no stop

- Keeps buying ladder and waits. Longest 200.65h (~8.4d). Only 2
  losers (-$4.50 2025-12-25, -$3.11 2026-03-10) are tiny taker exits,
  not systematic stops. 99.85% win = martingale accounting. Tail risk
  = drawdown deeper than ladder (~-26% now) forces bigger bag or loss.

### 2.5 Live snapshot (same logic now)

- Pos: 13.9 HYPE long @92.1758 ($1273 notion., -$8.64 uPnl).
- TP: A 13.9 @92.95 reduceOnly = +0.84% over entry.
- Ladder B (2026-09-19): 88.454x11.71(-4.04%) /86.572x21.96(-6.08%)
  /82.808x40.26(-10.16%) /79.044x75.03(-14.25%) /73.398x140.91(-20.37%)
  /67.752x265.35(-26.50%). Ladder notion. $40522.

## 3. What it is NOT

- Not short/hedged: zero shorts, funding paid -96.95 (longs pay).
  HYPE funding at snapshot +0.00125%.
- Not funding/basis arb: no spot HYPE (spot USDC $8088, HYPE 0).
- Not TWAP/VWAP/copy: twapId null all fills; sizes scale with equity.
- Not HFT: median 1h holds, 3166 maker fills.
- Not multi-strategy: HYPE-only 11 months. Transfers in
  userNonFundingLedgerUpdates ($2k-8k with 0x5c7c.., 0xafe6.. etc)
  just fund same bot; sizing growth tracks equity.

## 4. Economics and risk

- Edge ~0.84% -2*0.014% ~=0.81%/cycle; starter taker ~0.043% once so
  net ~0.78%. $1.30M notion. -> ~$5.2k net, matches.
- userFees maker dominance ex 2026-09-14 userAdd $7843 vs userCross $2369.
- Funding drag -$97/11mo ~1.8% of net, confirms perp-long bias.
- Risk is inventory/gap not leverage: 10x cosmetic (margin ~3% acct).
  -30% gap unfaded fills ~$40k ladder vs ~$12k equity = martingale ruin
  path. Mitigated by small starters (~2-3% equity) and wide deep steps.

## 5. Replication pseudocode

  UNIVERSE = HYPE-PERP only, LONG ONLY, cross 10x (use <5% margin)
  STARTER  = 2-3% equity (~$300 on $12k), TAKER buy (cross spread)
  TP       = reduceOnly maker @ vwap(buys)*1.0084, replace each buy fill
  LADDER   = maker bids at entry*[0.99,0.98,0.97,0.96,0.94,0.90,...]
             (first 3-4 steps -1.0%, deeper -2% to -4%)
  SIZES    = starter*[0.5,0.5,1,1,2,4,8,...] (~0.5/1.0/1.8/3.6x meas.)
  EXIT     = TP fills -> flat -> next STARTER immediately
  NO       = shorts, stops, triggers, TWAP, other coins

## 6. Verify

- python3 replicate_strategy.py replays fills (live fetch or cached
  json), rebuilds flat-to-flat cycles from startPosition, asserts
  HYPE-only, long-only, first-buy-taker ~99.9%, sell-maker ~98.7%,
  median markup ~0.84%, median grid step ~-1.0%, cycles ~1346,
  win-rate ~99.85%.
- Note: userFillsByTime caps 2000 rows; must paginate
  startTime=max(time)+1 (3 pages 2000+2000+876=4876). userFills alone
  misleads.

