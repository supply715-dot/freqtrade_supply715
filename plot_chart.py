import pandas as pd
import json
import zipfile
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# Load Data
data_path = Path("user_data/data/binance/futures/BTC_USDT_USDT-1h-futures.feather")
df = pd.read_feather(data_path)
df['date'] = pd.to_datetime(df['date'])
df.set_index('date', inplace=True)
df = df.loc['2025-05-10':'2026-05-10']

# Load Trades
zip_path = Path("user_data/backtest_results/backtest-result-2026-05-12_19-20-51.zip")
with zipfile.ZipFile(zip_path, 'r') as z:
    with z.open("backtest-result-2026-05-12_19-20-51.json") as f:
        data = json.load(f)
trades = pd.DataFrame(data['strategy']['FreqaiMacroRegimeStrategy']['trades'])
trades['open_date'] = pd.to_datetime(trades['open_timestamp'], unit='ms')
trades['close_date'] = pd.to_datetime(trades['close_timestamp'], unit='ms')
btc_trades = trades[trades['pair'] == 'BTC/USDT:USDT']

# Plotting
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(16, 8))
ax.plot(df.index, df['close'], color='#2c3e50', alpha=0.6, linewidth=1.5, label='BTC Price')

# Plot entries
longs = btc_trades[btc_trades['enter_tag'] == 'swing_long']
shorts = btc_trades[btc_trades['enter_tag'] == 'swing_short']

ax.scatter(longs['open_date'], longs['open_rate'], color='#2ecc71', marker='^', s=100, label='Long Entry', zorder=5)
ax.scatter(shorts['open_date'], shorts['open_rate'], color='#e74c3c', marker='v', s=100, label='Short Entry', zorder=5)

# Highlight winning/losing exits
winners = btc_trades[btc_trades['profit_ratio'] > 0]
losers = btc_trades[btc_trades['profit_ratio'] <= 0]

ax.scatter(winners['close_date'], winners['close_rate'], color='#f1c40f', marker='o', s=60, label='Take Profit', zorder=4)
ax.scatter(losers['close_date'], losers['close_rate'], color='#9b59b6', marker='X', s=80, label='Stop Loss', zorder=4)

ax.set_title('FreqAI 1h DCA Swing Bot - BTC/USDT Trade History (2025.05 ~ 2026.05)', fontsize=16, pad=20)
ax.set_ylabel('Price (USDT)', fontsize=12)
ax.grid(True, alpha=0.1)
ax.legend(loc='upper left', frameon=True, framealpha=0.9)

# Formatting dates
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax.xaxis.set_major_locator(mdates.MonthLocator())
plt.xticks(rotation=45)
plt.tight_layout()

import os
os.makedirs("user_data/plot", exist_ok=True)
output_path = r"C:\Users\7supp\.gemini\antigravity\260509_freqtrade\user_data\plot\backtest_chart.png"
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"Chart saved to {output_path}")
