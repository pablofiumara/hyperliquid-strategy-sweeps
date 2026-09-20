import json
import os
from collections import Counter, defaultdict
from datetime import datetime

all_fills = []
for i in range(5):
    path = f'/home/paf/Documents/code/misc/hyperliquid-strategy-sweeps/0x0bb81e516c88881c54529e1790470cb5e9f8740d/cline-solar-pro4/work/fills_page_{i}.json'
    if os.path.exists(path):
        with open(path) as f:
            data = json.load(f)
            if isinstance(data, list):
                all_fills.extend(data)
            else:
                print(f'Page {i}: unexpected format')

print(f'Total fills collected: {len(all_fills)}')

# Aggregate by coin
coin_counts = Counter(f['coin'] for f in all_fills)
print('\n=== Fills by Coin ===')
for coin, count in coin_counts.most_common():
    print(f'  {coin}: {count} fills')

# Aggregate PnL by coin
coin_pnl = defaultdict(float)
for f in all_fills:
    coin_pnl[f['coin']] += float(f.get('closedPnl', 0))
print('\n=== Closed PnL by Coin ===')
for coin, pnl in sorted(coin_pnl.items(), key=lambda x: -x[1]):
    print(f'  {coin}: {pnl:+.2f}')

total_pnl = sum(float(f.get('closedPnl', 0)) for f in all_fills)
print(f'\nTotal closed PnL: {total_pnl:+.2f}')

# Side distribution
sides = Counter(f['side'] for f in all_fills)
print('\n=== Side Distribution ===')
for side, count in sides.most_common():
    if side == "B":
        print(f'  Buy: {count}')
    else:
        print(f'  Sell: {count}')

# Direction distribution
dirs = Counter(f['dir'] for f in all_fills)
print('\n=== Direction Distribution ===')
for d, count in dirs.most_common():
    print(f'  {d}: {count}')

# Fee analysis
total_fees = sum(float(f.get('fee', 0)) for f in all_fills)
print(f'\nTotal fees: {total_fees:.2f} USDC')

# Time range
times = [f['time'] for f in all_fills]
if times:
    start = datetime.fromtimestamp(min(times)/1000)
    end = datetime.fromtimestamp(max(times)/1000)
    print(f'\nTime range: {start} to {end}')
    print(f'Duration: {(max(times)-min(times))/86400000:.1f} days')

# Per-coin detail
print('\n=== Per-Coin Detail ===')
for coin in sorted(coin_counts):
    coin_fills = [f for f in all_fills if f['coin'] == coin]
    buys = sum(1 for f in coin_fills if f['side']=='B')
    sells = sum(1 for f in coin_fills if f['side']=='A')
    coin_pnl_val = sum(float(f.get('closedPnl', 0)) for f in coin_fills)
    coin_fees = sum(float(f.get('fee', 0)) for f in coin_fills)
    sz_total = sum(float(f['sz']) for f in coin_fills)
    print(f'{coin}: {len(coin_fills)} fills, {buys} buys, {sells} sells, PnL: {coin_pnl_val:+.2f}, Fees: {coin_fees:.2f}, Total sz: {sz_total:.2f}')

# Analyze trade patterns - find sequences
print('\n=== Trade Pattern Analysis ===')
for coin in sorted(coin_counts):
    coin_fills = sorted([f for f in all_fills if f['coin'] == coin], key=lambda x: x['time'])
    if len(coin_fills) < 2:
        continue
    print(f'\n{coin} trade sequence ({len(coin_fills)} fills):')
    for f in coin_fills[:10]:
        if f['side'] == 'B':
            side = 'BUY'
        else:
            side = 'SELL'
        print(f"  {datetime.fromtimestamp(f['time']/1000)}: {side} {f['sz']} @ {f['px']} | {f['dir']} | PnL: {float(f.get('closedPnl',0)):+.2f}")
    if len(coin_fills) > 10:
        print(f'  ... and {len(coin_fills)-10} more fills')
