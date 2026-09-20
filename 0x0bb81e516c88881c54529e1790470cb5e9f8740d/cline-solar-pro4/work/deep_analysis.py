import json
import os
from collections import Counter, defaultdict
from datetime import datetime
import statistics

all_fills = []
for i in range(5):
    path = f'/home/paf/Documents/code/misc/hyperliquid-strategy-sweeps/0x0bb81e516c88881c54529e1790470cb5e9f8740d/cline-solar-pro4/work/fills_page_{i}.json'
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            if isinstance(data, list):
                all_fills.extend(data)

hype_fills = sorted([f for f in all_fills if f['coin'] == 'HYPE'], key=lambda x: x['time'])

print("=== STRATEGY DEEP ANALYSIS ===\n")

# Size analysis
print("=== SIZE ANALYSIS ===")
sizes = [float(f['sz']) for f in hype_fills]
print(f"Size stats: min={min(sizes):.2f}, max={max(sizes):.2f}, mean={statistics.mean(sizes):.2f}, median={statistics.median(sizes):.2f}")

size_buckets = Counter()
for s in sizes:
    if s < 1:
        size_buckets['<1'] += 1
    elif s < 2:
        size_buckets['1-2'] += 1
    elif s < 5:
        size_buckets['2-5'] += 1
    elif s < 10:
        size_buckets['5-10'] += 1
    elif s < 50:
        size_buckets['10-50'] += 1
    else:
        size_buckets['50+'] += 1

print("\nSize distribution:")
for bucket in ['<1', '1-2', '2-5', '5-10', '10-50', '50+']:
    print(f"  {bucket}: {size_buckets.get(bucket, 0)} fills")

# PnL distribution
print("\n=== PnL ANALYSIS ===")
pnls = [float(f.get('closedPnl', 0)) for f in hype_fills]
positive_pnls = [p for p in pnls if p > 0]
negative_pnls = [p for p in pnls if p < 0]
zero_pnls = [p for p in pnls if p == 0]

print(f"Positive PnL fills: {len(positive_pnls)} (total: {sum(positive_pnls):+.2f})")
print(f"Negative PnL fills: {len(negative_pnls)} (total: {sum(negative_pnls):+.2f})")
print(f"Zero PnL fills: {len(zero_pnls)}")

if positive_pnls:
    print(f"Avg winning trade: {statistics.mean(positive_pnls):.2f}")
    print(f"Max win: {max(positive_pnls):.2f}")
if negative_pnls:
    print(f"Avg losing trade: {statistics.mean(negative_pnls):.2f}")
    print(f"Max loss: {min(negative_pnls):.2f}")

# Time-based analysis
print("\n=== TIME-BASED ANALYSIS ===")
daily_trades = defaultdict(list)
for f in hype_fills:
    dt = datetime.fromtimestamp(f['time']/1000)
    day_key = dt.strftime('%Y-%m-%d')
    daily_trades[day_key].append(f)

print(f"Trading days: {len(daily_trades)}")
daily_counts = [len(trades) for trades in daily_trades.values()]
print(f"Trades per day: min={min(daily_counts)}, max={max(daily_counts)}, mean={statistics.mean(daily_counts):.1f}, median={statistics.median(daily_counts):.1f}")

print("\nTop 10 busiest trading days:")
sorted_days = sorted(daily_trades.items(), key=lambda x: -len(x[1]))[:10]
for day, fills in sorted_days:
    day_pnl = sum(float(f.get('closedPnl', 0)) for f in fills)
    day_fees = sum(float(f.get('fee', 0)) for f in fills)
    print(f"  {day}: {len(fills)} fills, PnL: {day_pnl:+.2f}, Fees: {day_fees:.2f}")
