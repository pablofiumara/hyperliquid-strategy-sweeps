# Strategy description for this wallet — cline-deepseek-v4.1-flash

(salvaged from output.txt deep-analysis blocks; model used submit_and_exit so no work/*.md was written)

**Strategy 1 (core, since Mar 13; runs through today): long-only, 1x, buy-the-dip swing scalping on liquid alts with passive limit ladders.**
- Instruments: HYPE perp (Mar–Sep, 568 fills, +$495), XMR (Aug 25–Sep 21, 505 fills, +$105), NEAR (Sep 8–26, 295 fills, +$216), ZEC (Aug 31–Sep 4 burst, +$22), INJ (+$56), ZRO (+$37), ONDO (+$40), JUP (+$19), UNI (+$22), XLM (+$10), ETH (6 fills, +$0.4).
- Direction: long only in practice — exactly 4 short fills ever (2 small HYPE shorts May 19/30, both profitable, total ~$1.6 profit, ~$130 notional) = essentially hedges/scalps.
- Mechanics: 1,702 buys vs 648 sells; median buy $35 (p25–p75 $28–49) vs median sell $73 ($40–146) → scale in small clips, scale out in ~2.5x larger chunks. 73% maker fills overall (HYPE 42% taker; @107 5%).
- Laddering: consecutive buy prices step down median -0.37% (p25 -0.95%) → averaging down into weakness; 99% of completed cycles have the last buy below the first. Resting bids now visible live: 22 open orders = 1–4 bids per coin ($32–192) + one take-profit ask per coin ($25–399).
- Exits into strength: sell price vs average buy price +0.5% (XMR/ZEC) to +2.4% (HYPE spot), i.e., they harvest small bounces. Cycle stats: 479 full round trips; median duration 1.6 h (p75 6.5 h, p90 24 h); median 3 buys per cycle; median cycle profit $0.3–2.8 by coin. Win rate 99.5%, so no stop-losses — they wait/scale instead.
- Exposure: 5–30% of equity per coin (peak positions $107–717), 5–7 coins at once, 1x cross, fully employed (withdrawable $8; margin used $1,354 ≈ 62% of equity + resting orders reserve the rest). Time with an open position: 90–100% per coin — continuously long.
- Timing: fills spread across all 24 UTC hours with a daytime peak 11:00–20:00 UTC (121–180 fills/h); median gap between fills in the same coin ~10 min; bursts of ladder fills (16% <10s). 161 active days of 246; 14.6 fills/active day; Sep = 59 fills/day, 78% of all September fills.

The big picture is clear:
- Long-only (only 4 short fills on HYPE ever), altcoin swing/scalp with many small limit buys (median $35 buy, median $73 sell), scaling in with 20-50% taker, selling into strength at +0.5–2.4% premium over average buy; ~99.5% of closing fills profitable; total closed pnl $1135 vs fees $31 vs funding -$21.
- 161 active days of 246; activity in bursts; UTC hours spread across the day (peak 11–20 UTC).
- Median gap between fills within a coin ~10 min; 16% within 10s (rapid ladder fills), 30% > 1h.
- Equity: allTime account value from 0 (Jan 28) to ~$2194; max DD -9.1%; PnL allTime $1012.5 (per portfolio), volume $141.5k (spot+perp), perp volume $131.8k.
- Deposits + sends in: 20.9 + 472.9 + 493.8 (internal transfer in) + 200 + 200 + 601.83*3 = wait, those 3 entries at same nonce-ish times... maybe payouts from vault or subaccount. All destination = this address, so all are INCOMING transfers. Total incoming: 20.9+472.9+493.8+200+200+601.83*3+557.03+129.6 = 20.937249+472.873007 = 493.81 (deposits) + 493.81 + 200 + 200 + 1805.49 + 557.03 + 129.6 = 3879.74 total in. Minus pnl 1012 = ... account value now 2193 means net out? No, all these are incoming (destination = user). So inflows ≈ 3879.74. Equity 2194 + pnl? Wait pnl allTime 1012.5 was measured with net deposits? The portfolio pnlHistory typically = account value change adjusted for deposits/withdrawals... AllTime pnl 1012.5 with av starting at 0. If av started 0 and now 2194, and net deposits were 3879.74, then trading pnl = 2194 - 3879.74 = -1685?? That contradicts. Unless pnlHistory excludes deposit effects and deposits were much lower. Hmm.

**Trade mechanics**
- 2350 fills: 1702 buys / 648 sells (72%/28%); buy notional $70.9k, sell notional $70.6k.
- Median buy $35, median sell $73 (25th–75th: buys $28–49, sells $40–146): scale-in in small clips, scale-out in chunks ~2-2.6x larger.
- 27% of fills taker overall; @107 5%, XMR 20%, HYPE 42%.
- Consecutive buy fills spaced -0.37% median (p25 -0.95%): they add on the way DOWN (99% of completed cycles have last buy below first buy = martingale/averaging down on dips).
- Consecutive sell fills median 0.00% gap: sell chunks at same/similar price level (or single sells).
- 479 completed round-trip cycles (position opened → fully closed), median duration 1.6 h (p75 6.5 h, p90 24 h), median 3 buys per cycle.
- Avg round trip pnl tiny: median $0.3–2.8 depending on coin; win rate 645/648 (99.5%) closes profitable; median close +$1.07, max +$23.7; avg sell price premium vs avg buy price +0.5% (XMR/ZEC) to +2.4% (HYPE spot @107).
- Time with an open position: 90–100% of the span per coin — they're virtually always long something, i.e., continuous market presence, not opportunistic one-offs.
- Working now: 22 open limit orders: 1–4 bids per coin ($32–192 each) plus 1 resting ask per coin ($25–399) — live ladder of passive bids + take-profit asks.
- UTC hour distribution fairly uniform but peaks 11:00–20:00 UTC (121–180 fills/h) — active mostly during US/Europe hours; still fills around the clock (bot-like).
- Median gap between fills in same coin ~10 min; 16% within 10s (ladder swept), 30% > 1h.

**Coins / sequence (campaign structure)**
- Jan 23–May 23: only HYPE spot (@107), buy range $21.15–57.97 — accumulated through the run from ~$21 to ~$58, holding 100% of the time. Monthly: Jan 21 fills/$1.3k vol, Feb 72/$4.6k, Mar 85/$5.3k, Apr 30/$2.1k, May 126/$11.4k. Total @107: 155 fills, $4.8k buys/$4.9k sells, +$112 pnl, 5% taker (maker-only accumulation). Note @107 gain is where the initial capital grew (Feb 13: 200 spot→perp, Mar 13: 601.83 spot→perp — funded perp trading from spot profits; equity nearly tripled from $494 by Mar).
- Mar 13: starts HYPE perp; runs HYPE campaign through Sep 24 (568 fills, $25.7k buys/$25.8k sells, +$495 pnl, biggest single-coin profit, 150 round trips). Adds two small shorts in May (hedges/scalps) — only negatives ever traded, both won.
- May 23: stops HYPE spot trading (probably sold) — last @107 fill.
- Aug 25: starts XMR campaign (as XMR ran hot): 505 fills in 4 weeks, $13.9k per side, +$105, 66 cycles, 20% taker.
- Aug 31–Sep 4: ZEC burst (185 fills in 4 days, +$21.8, 39 cycles).
- Sep 6–9: JUP (78 fills, 3 days), ETH (6 fills), XLM (23 fills), and NEAR (Sep 8 onward, 295 fills through Sep 26, +$216, 66 cycles).
- Sep 18–25: INJ, UNI, ZRO, ONDO added; Sep 9 ONDO.
- Sep: 11 coins, 1479 fills, $75k volume, +$564 closed pnl — 2-4x the prior monthly pace; volume ramped as capital grew (deposits of 557 + 130 enabling bigger size).
- September campaign: 5-11 coins simultaneously, capital fully utilized (1x, ~$1.35k positions vs $2.2k equity).
