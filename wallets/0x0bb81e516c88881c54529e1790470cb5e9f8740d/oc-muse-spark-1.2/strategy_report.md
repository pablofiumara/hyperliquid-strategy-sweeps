# Strategy description for this wallet — oc-muse-spark-1.2

# source: final answer in output.txt

### 1. Core Idea
Fixed-% mean-reversion grid that `DCA` / averages down on dips and takes profit at `+0.84%` over volume-weighted average entry. High win-rate, unbounded martingale tail.

`avg TP 0.844% median 0.8399% stdev 0.13% min 0.832% max 4.07%` over `1347` reconstructed rounds (`detailed_rounds:1443`).

### 2. Entry
* After every `Close Long` to `0` (`startPosition == sz` verified), immediately `B` market (`crossed:true` fee `~0.043%`) ~`$340-350` (~`3.6-4.1 HYPE` at `90-94`) e.g. `2026-09-19 02:53:28 3.66@94.125`.
* Simultaneously plants `6` deep + `3-5` near-price `Gtc Limit B` (maker fee `~0.014%`) in cluster within `2s` (`historicalOrders:1282` -> `clusters 50` `Counter({22:48})`). Refreshed every fill.

Current open ladder (`openOrders:1`) at `mark 91.10`:
```
88.454 x11.71 $1035  -2.91%
86.572 x21.96 $1901  -4.98%  ratio 1.88
82.808 x40.26 $3333  -9.11%  ratio 1.83
79.044 x75.03 $5930 -13.24%  ratio 1.86
73.398 x140.91 $10342 -19.44% ratio 1.88
67.752 x265.35 $17978 -25.63% ratio 1.88
```
Plus near-price: `93.159/92.218 x1.83 (-1%)`, `91.277/90.336 x3.29 (-1%)` -> drop `1.01-1.02%` near, `2.13-7.69%` deep, size `~1.85x` geometric. Early era same multipliers, smaller USD (`42/84/148/939/1647` at `2025-10-13` 5-level `41.635->39.96`).

`61/4876` `B` fills are `liquidation` (`liquidatedUser` `markPx` `market`) - limit bids intentionally sit where liquidations trigger, harvesting wick.

### 3. Exit
Single `A reduceOnly Limit` at `avg*1.0084`:
```
TP = VWAP(opens) * 1.00839
```
Verified `92.1758*1.0084=92.95` matches `oid 550321849509 limitPx 92.95 sz13.9`. All closes `reduceOnly:true`, `crossed:false`.

### 4. Sizing Dynamics
```
Round n=1: 210 rounds avg $75-343 cost pnl $2.88
n=2: 116 rounds pnl $4.31 (e.g. 3.67@93.649+1.83@92.802 ->5.5@94.151 +$4.31)
n=5: 86 rounds e.g. 3.78@87.774+1.89@86.896+1.89@86.018+3.4@85.14+3.4@84.263 -> +$2.88
n=10: max 280.78 sz @30.11 avg -> 28.23 trough -528 unreal, close 30.36 +69.94
```
USD per deep level doubles: `1035->1901->3333->5930->10342->17978`. Total ladder notional `~$38.5k` vs `accountValue ~$4.2k` - martingale relies on recovery before deeper levels fill.

### 5. Bot Fingerprint
`historicalOrders` shows paired `canceled/open` at same `timestamp` (order amendment), `22` orders per grid (`11*2`), `A clusters 102` (TP), median inter-fill `9.75min` avg `86.8min`. Fill side `B 1405 A 595` in last `2000`.

### 6. Risk / Performance
```
total closedPnl 5458.12
fees 268.42 -> net 5189.69
funding -96.94 -> 5092.75
wins 1440 losses 3 winRate 99.79% profitFactor 717.8 avgWin 3.79 avgLoss -2.53
negatives: 2025-12-?? 10.68@~24.9 ->24.658 -$4.50 (2 legs), 2026-03 14.15@34.6 ->34.16 -$3.11 market
maxPos 280.78 @30.11 (2025-??) notion ~$8448
maxDD proxy 579.63 (221.61@57.85 avg 57.85 ->55.235 on 2026-06-10 05:13:25)
```
No stop. Drawdown held. Current `ROE -11.6%` on open. Liquidation `None` (cross margin healthy `marginUsed 126/4229` ~`3%`, effective `~0.3x`).

### 7. Replication Pseudocode
```python
coin="HYPE"; leverage=10; tp=0.0084
grid_pct=[0.01,0.01,0.01,0.02,0.04,0.045,0.071,0.076] # near->deep
grid_mult=1.85 # per deep level
on_close_to_zero():
  avg, pos = VWAP(opens), sum(sz)
  place limit B ladder below mark using grid_pct/grid_mult
  place limit A reduceOnly at avg*(1+tp)
on_fill(B): recalc avg, update TP order
```

### 8. Caveats
* HyperX `No trading data available` is frontend bug - on-chain proves activity.
* Pure martingale, no hedge: `-40%` trending crash without `+0.84%` bounce = catastrophic; funding drag `~11% APR` long.
* Profit cycling: `16028` deposits in, `14472+549` out, `internalTransfer 2000` - `accountValue` not pure ROI.

In short: single-strategy automated HYPE long grid, market entry + layered limit DCA averaging down `1.85x`, fixed `0.84%` grid take-profit as liquidation liquidity provider.
