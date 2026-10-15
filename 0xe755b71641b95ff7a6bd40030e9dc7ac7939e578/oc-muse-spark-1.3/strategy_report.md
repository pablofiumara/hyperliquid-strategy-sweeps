# Strategy description for this wallet — oc-muse-spark-1.3

## 1. Account snapshot

* Perp `accountValue ~$2,181`, total long notional `~$1,353`, margin used same (all 1x cross).
* Current 7 positions, all long, all 1x cross, no liquidation px:
  `INJ 29, UNI 13, ZRO 14.9, NEAR 77.8, ONDO 145, HYPE 3.51, XMR 0.351`
* Spot: `~$2,193 USDC` + dust HYPE, no other spot inventory.
* `portfolio`: first funded `2026-01-28`, `$0 -> ~$2,193` now. `allTime vol ~$141k` (`perp ~$132k`), `allTime pnl ~+$1,013` (`perp ~+$893`). `month pnl ~+$520`, `week ~+$226`. Month/allTime pnl never negative — steady grind.

## 2. Full fill history: 2,351 fills, Jan-Sep 2026

* `Open Long 1,597 / Close Long 595 / Spot Buy 104 / Spot Sell 51 / Open Short 2 / Close Short 2`
* I.e. `99.8%` long/spot-buy, `0.17%` short (2 tiny HYPE round-trips: `0.61 @ ~48 held ~30m +$0.38`, `1.46 @ ~68 held ~1.7h +$1.19`, both taker). No short strategy.
* `@107` = HYPE/USDC spot (universe 107 -> token 150 HYPE). All 155 `@107` fills are Jan-Apr HYPE spot, `pnl ~+$112`.
* Recent 2,000-fill window `2026-06-02 to 2026-09-26`, 11 perp coins, zero shorts:
  `XMR 505, HYPE 373, NEAR 295, ZEC 185, INJ 159, ZRO 158, ONDO 154, JUP 78, UNI 64, XLM 23, ETH 6`
* Per-coin buy vs sell notional almost balanced (net `-$78 to +$187`), i.e. rotating, not buy-and-hold one coin.

## 3. Signature: long-only 1x grid / DCA scalp bot

* `73% maker` (`crossed=false`), `0 TWAP`, 3 repeating `cloid` prefixes — passive limit ladder.
* Tiny size: `avg ~$58/fill, median ~$36, p10 ~$15.6, p90 ~$112.6, max ~$710`.
* Only `415/1,483` opens start from flat; `72%` add to existing position = scaling / averaging down.
* Closes are tiny take-profits: `mean +$1.68/close, median +$0.99`, `mean +1.5%` of notional. Weighted close px `0.5-1.7%` above weighted open px per coin (e.g. HYPE `+1.5%`, XMR `+0.5%`, ZEC `+0.5%`).
* Win rate `514/517 = 99.4%` profitable closes; only 3 losses (`-$8.2, -$2.2, -$1.25`). Per-coin `97-100%`. Never realizes losers — holds/averages instead.
* Round-trips frequent: `5-80` flats/coin in window. Median hold `ZRO 1.0h, INJ 1.2h, NEAR 1.6h, XMR 3.0h, HYPE 10h`; mean longer due to bag-holds to `35d` max. Min minutes.
* Total `closedPnl ~+$1,135`, fees `~$31`, funding paid `~-$20.9` (long bias cost, mostly HYPE+XMR). Funding arbitrage ruled out.
* Activity bot-like: `78/116` days active, `~26 fills/day`, bursts `100-156/day`, all 24h UTC, slight 11-18 UTC peak. Median inter-fill `~4.4 min`.

Evolution: `Jan-Mar HYPE spot accumulation -> Mar-Jun HYPE perps -> Jun-Sep diversified 11-coin long grid`. Current book is same: diversified 1x longs.

**Strategy:** automated long-only, ~1x, multi-coin (privacy + alt-L1 heavy: XMR/HYPE/NEAR/ZEC/INJ) buy-the-dip grid. Lays passive micro-orders, scales into dips, sells `~1%` bounces, almost never takes a loss, uses 1x so drawdowns can be held for hours-weeks.
