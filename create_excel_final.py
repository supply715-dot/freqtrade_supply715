import json
import pandas as pd
import zipfile
import os
import glob

def extract_and_convert():
    # Find the latest zip file in backtest_results
    result_dir = 'user_data/backtest_results/'
    zip_files = glob.glob(os.path.join(result_dir, 'backtest-result-*.zip'))
    if not zip_files:
        print("No backtest zip files found.")
        return
    
    latest_zip = max(zip_files, key=os.path.getmtime)
    print(f"Using latest result: {latest_zip}")
    
    # Extract zip
    with zipfile.ZipFile(latest_zip, 'r') as z:
        # Freqtrade result zips contain a .json file with the result
        # Find the .json file inside the zip
        json_files = [f for f in z.namelist() if f.endswith('.json')]
        if not json_files:
            print("No JSON found in zip.")
            return
        
        with z.open(json_files[0]) as f:
            data = json.load(f)
    
    # Extract trades
    # Structure: data['strategy']['SwingTrendRiderV4_FreqAI_20260515']['trades']
    strategy_name = 'SwingTrendRiderV4_FreqAI_20260515'
    strategy_results = data.get('strategy', {}).get(strategy_name, {})
    trades = strategy_results.get('trades', [])
    
    if not trades:
        print(f"No trades found for strategy {strategy_name}")
        return

    report_data = []
    cum_profit_usdt = 0.0
    initial_balance = 1000.0
    
    for t in trades:
        profit_usdt = t.get('profit_abs', 0)
        cum_profit_usdt += profit_usdt
        
        open_date = pd.to_datetime(t['open_date'])
        close_date = pd.to_datetime(t['close_date'])
        duration = close_date - open_date
        
        report_data.append({
            '진입시간': t['open_date'],
            '종료시간': t['close_date'],
            '진입가격': t['open_rate'],
            '종료가격': t['close_rate'],
            '포지션': 'Long' if t.get('is_short', False) == False else 'Short',
            '보유시간': str(duration),
            '수익금(USDT)': round(profit_usdt, 2),
            '누적수익금(USDT)': round(cum_profit_usdt, 2),
            '누적수익률(%)': round((cum_profit_usdt / initial_balance) * 100, 2)
        })
    
    df = pd.DataFrame(report_data)
    output_file = 'btc_v4_trade_history_5y.xlsx'
    df.to_excel(output_file, index=False)
    print(f"Excel report created: {output_file}")

if __name__ == "__main__":
    extract_and_convert()
