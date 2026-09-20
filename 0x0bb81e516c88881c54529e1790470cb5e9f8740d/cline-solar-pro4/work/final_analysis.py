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

print("=== ENTRY/EXIT PATTERN ANALYSIS ===\n")

# Track position build-up and scale-out patterns
print("=== POSITION CYCLE ANALYSIS (sample of first 50 trades) ===")
position = 0.0
entry_px_sum = 0.0
entry_count = 0

for i, f in enumerate(hype_fills[:50]):
    sz = float(f['sz'])
    px = float(f['px'])
    direction = f['dir']
    pnl = float(f.get('closedPnl', 0))
    
    if direction == 'Open Long':
        entry_px_sum += px * sz
        entry_count += 1
        position += sz
        avg_entry = entry_px_sum / entry_count if entry_count > 0 else 0
        print(f"{i+1}. OPEN: +{sz:.2f} @ {px:.2f} | Pos: {position:.2f} | Avg Entry: {avg_entry:.2f}")
    else:  # Close Long
        position -= sz
        if position < 0:
            position = 0
        print(f"{i+1}. CLOSE: -{sz:.2f} @ {px:.2f} | Pos: {position:.2f} | PnL: {pnl:+.2f}")

# Analyze closed position PnLs
print("\n=== CLOSED POSITION ANALYSIS ===")
closed_positions = []
current_position = 0.0
current_entry_sum = 0.0
current_entry_count = 0

for f in hype_fills:
    sz = float(f['sz'])
    px = float(f['px'])
    direction = f['dir']
    pnl = float(f.get('closedPnl', 0))
    
    if direction == 'Open Long':
        current_entry_sum += px * sz
        current_entry_count += 1
        current_position += sz
    elif direction == 'Close Long':
        if current_position > 0 and pnl > 0:
            avg_entry = current_entry_sum / current_entry_count if current_entry_count > 0 else 0
            closed_positions.append({
                'pnl': pnl,
                'size_closed': sz,
                'remaining_position': current_position - sz
            })
        current_position = max(0, current_position - sz)

print(f"Total profitable closes: {len(closed_positions)}")
if closed_positions:
    pnls = [c['pnl'] for c in closed_positions]
    print(f"PnL stats: min={min(pnls):.2f}, max={max(pnls):.2f}, mean={statistics.mean(pnls):.2f}, median={statistics.median(pnls):.2f}")
    print(f"Total PnL: {sum(pnls):+.2f}")

# Entry vs exit price relationship
print("\n=== ENTRY/EXIT PRICE SPREAD ===")
# Find pairs of opens and closes
opens = [(f['time'], float(f['px']), float(f['sz'])) for f in hype_fills if f['dir'] == 'Open Long']
closes = [(f['time'], float(f['px']), float(f['sz']), float(f.get('closedPnl', 0))) for f in hype_fills if f['dir'] == 'Close Long']

print(f"Total opens: {len(opens)}")
print(f"Total closes: {len(closes)}")
print(f"Ratio (closes/opens): {len(closes)/len(opens):.2f}")

# Price movement analysis
print("\n=== PRICE MOVEMENT DURING TRADES ===")
# Sample entries and subsequent price action
sample_entries = opens[:20]
for entry_time, entry_px, entry_sz in sample_entries:
    entry_dt = datetime.fromtimestamp(entry_time/1000)
    # Find closes after this entry
    subsequent_closes = [c for c in closes if c[0] > entry_time]
    if subsequent_closes:
        first_close = subsequent_closes[0]
        close_px = first_close[1]
        pnl = first_close[3]
        spread_pct = (close_px - entry_px) / entry_px * 100
        print(f"Entry: {entry_dt} @ {entry_px:.2f} -> First close: {close_px:.2f} | Spread: {spread_pct:+.2f}% | PnL: {pnl:+.2f}")

# Volume pattern
print("\n=== VOLUME/SIZE PATTERN ===")
# Check if there's a pattern of consistent sizing
sizes_by_action = {'open': [], 'close': []}
for f in hype_fills:
    sz = float(f['sz'])
    if f['dir'] == 'Open Long':
        sizes_by_action['open'].append(sz)
    else:
        sizes_by_action['close'].append(sz)

print(f"Open sizes: mean={statistics.mean(sizes_by_action['open']):.2f}, median={statistics.median(sizes_by_action['open']):.2f}")
print(f"Close sizes: mean={statistics.mean(sizes_by_action['close']):.2f}, median={statistics.median(sizes_by_action['close']):.2f}")

# Check cross vs non-crossed trades
print("\n=== CROSS VS NON-CROSSED ===")
crossed = sum(1 for f in hype_fills if f.get('crossed', False))
not_crossed = sum(1 for f in hype_fills if not f.get('crossed', False))
print(f"Crossed (market): {crossed}")
print(f"Not crossed (limit): {not_crossed}")

# Fee analysis relative to PnL
print("\n=== FEE EFFICIENCY ===")
total_fees = sum(float(f.get('fee', 0)) for f in hype_fills)
total_pnl = sum(float(f.get('closedPnl', 0)) for f in hype_fills)
fee_to_pnl_ratio = total_fees / total_pnl * 100 if total_pnl > 0 else 0
print(f"Total fees: {total_fees:.2f} USDC")
print(f"Total PnL: {total_pnl:+.2f}")
print(f"Fee/PnL ratio: {fee_to_pnl_ratio:.2f}%")

# Win rate by closed position
print("\n=== WIN/LOSS STATISTICS ===")
profitable_closes = [c for c in closed_positions if c['pnl'] > 0]
loss_closes = [c for c in closed_positions if c['pnl'] <= 0]
if closed_positions:
    win_rate = len(profitable_closes) / len(closed_positions) * 100
    print(f"Win rate: {win_rate:.1f}% ({len(profitable_closes)}/{len(closed_positions)})")
    if loss_closes:
        print(f"Loss count: {len(loss_closes)}")
    else:
        print("No losses on closed positions!")
