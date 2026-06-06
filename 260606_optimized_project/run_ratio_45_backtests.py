import json
import os
import shutil
import zipfile
import pandas as pd
import subprocess
import copy

# 경로 정의
WORKSPACE_DIR = r"c:\Users\7supp\.gemini\antigravity\260509_freqtrade"
RESULTS_DIR = os.path.join(WORKSPACE_DIR, "user_data", "backtest_results")
OUTPUT_DIR = r"C:\Users\7supp\.gemini\antigravity\brain\2f364b73-3d77-4327-8238-0b87f4d0b8e3"

CONFIG_BTC_PATH = os.path.join(WORKSPACE_DIR, "config_bt_btc.json")
CONFIG_ETH_PATH = os.path.join(WORKSPACE_DIR, "config_bt_eth.json")

def backup_and_modify_configs():
    # 백업 생성
    shutil.copy2(CONFIG_BTC_PATH, CONFIG_BTC_PATH + ".bak")
    shutil.copy2(CONFIG_ETH_PATH, CONFIG_ETH_PATH + ".bak")
    print("Configs backed up.")

    # BTC 수정
    with open(CONFIG_BTC_PATH, "r", encoding="utf-8") as f:
        btc_cfg = json.load(f)
    btc_cfg["tradable_balance_ratio"] = 0.45
    with open(CONFIG_BTC_PATH, "w", encoding="utf-8") as f:
        json.dump(btc_cfg, f, indent=4)

    # ETH 수정
    with open(CONFIG_ETH_PATH, "r", encoding="utf-8") as f:
        eth_cfg = json.load(f)
    eth_cfg["tradable_balance_ratio"] = 0.45
    with open(CONFIG_ETH_PATH, "w", encoding="utf-8") as f:
        json.dump(eth_cfg, f, indent=4)
    print("Configs modified to 0.45 ratio.")

def restore_configs():
    if os.path.exists(CONFIG_BTC_PATH + ".bak"):
        shutil.move(CONFIG_BTC_PATH + ".bak", CONFIG_BTC_PATH)
    if os.path.exists(CONFIG_ETH_PATH + ".bak"):
        shutil.move(CONFIG_ETH_PATH + ".bak", CONFIG_ETH_PATH)
    print("Configs restored to original.")

def run_backtest(config_file, freqai_config):
    cmd = [
        r"C:\python_3_13_3_win64\Scripts\freqtrade.exe",
        "backtesting",
        "--strategy", "V8_BTC_ETH_optimized",
        "--config", config_file,
        "--config", freqai_config,
        "--timerange", "20220601-20260601",
        "--freqaimodel", "LightGBMRegressor"
    ]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=WORKSPACE_DIR, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        print(f"Error executing backtest for {config_file}:")
        print(result.stderr)
        raise RuntimeError("Backtest execution failed.")
    print(f"Successfully finished backtest for {config_file}.")

def get_latest_results(n=2):
    # RESULTS_DIR 에서 최근 파일 n개 찾기
    files = [os.path.join(RESULTS_DIR, f) for f in os.listdir(RESULTS_DIR) if f.endswith(".zip")]
    files.sort(key=os.path.getmtime, reverse=True)
    return files[:n]

def parse_zip(path):
    with zipfile.ZipFile(path, 'r') as zip_ref:
        main_data = None
        for name in zip_ref.namelist():
            if name.endswith('.json') and not name.endswith('_config.json') and not name.endswith('_metadata.json') and not name.endswith('.meta.json'):
                main_data = json.loads(zip_ref.read(name))
                break
        if main_data:
            strategy_name = list(main_data['strategy'].keys())[0]
            strategy_data = main_data['strategy'][strategy_name]
            trades = strategy_data.get('trades', [])
            df = pd.DataFrame(trades)
            if not df.empty:
                df['close_date'] = pd.to_datetime(df['close_date'])
                df['open_date'] = pd.to_datetime(df['open_date'])
            summary = main_data['strategy_comparison'][0]
            return df, summary
    return pd.DataFrame(), {}

def simulate_portfolio(btc_trades, eth_trades):
    # 포트폴리오 통합 성과 시뮬레이션 (10,000 USDT 기준 복리)
    # 두 트레이드 병합 및 시간순 정렬
    btc_df = btc_trades.copy()
    btc_df['coin'] = 'BTC'
    eth_df = eth_trades.copy()
    eth_df['coin'] = 'ETH'
    
    merged_trades = pd.concat([btc_df, eth_df], ignore_index=True)
    
    # 시간 순 정렬을 위해 이벤트 화
    events = []
    for idx, row in merged_trades.iterrows():
        close_time = row['close_date']
        if row['open_date'] == row['close_date']:
            close_time = close_time + pd.Timedelta(seconds=1)
            
        events.append({
            'time': row['open_date'],
            'type': 'open',
            'coin': row['coin'],
            'trade_id': idx,
            'profit_ratio': row['profit_ratio']
        })
        events.append({
            'time': close_time,
            'type': 'close',
            'coin': row['coin'],
            'trade_id': idx,
            'profit_ratio': row['profit_ratio']
        })
        
    # 시간 순 정렬 (시간이 같은 경우 close 이벤트를 먼저 처리하여 잔고 확보)
    events.sort(key=lambda x: (x['time'], 0 if x['type'] == 'close' else 1))
    
    initial_balance = 10000.0
    balance = initial_balance
    peak = initial_balance
    mdd = 0.0
    
    active_positions = {} # trade_id -> stake_amount
    balance_history = []
    
    for ev in events:
        t = ev['time']
        t_id = ev['trade_id']
        
        if ev['type'] == 'open':
            # 지갑 잔고의 45%를 투자금으로 설정
            stake = balance * 0.45
            balance -= stake
            active_positions[t_id] = stake
        elif ev['type'] == 'close':
            if t_id in active_positions:
                stake = active_positions.pop(t_id)
                pnl = stake * ev['profit_ratio']
                balance += (stake + pnl)
                
        # 리스크 지표 업데이트
        if balance > peak:
            peak = balance
        drawdown = (peak - balance) / peak
        if drawdown > mdd:
            mdd = drawdown
            
        balance_history.append({'time': t, 'balance': balance})
        
    final_profit_pct = (balance - initial_balance) / initial_balance * 100
    return final_profit_pct, mdd * 100, balance - initial_balance

def main():
    try:
        backup_and_modify_configs()
        
        # 백테스트 기동
        print("Starting BTC 72h ratio 0.45 backtest...")
        run_backtest("config_bt_btc.json", "config_freqai_bt_btc_72h.json")
        
        print("Starting ETH 24h ratio 0.45 backtest...")
        run_backtest("config_bt_eth.json", "config_freqai_bt_eth_24h.json")
        
    finally:
        restore_configs()
        
    # 결과 파싱
    latest_files = get_latest_results(2)
    print(f"Latest backtest result files found: {latest_files}")
    
    btc_df, btc_sum = pd.DataFrame(), {}
    eth_df, eth_sum = pd.DataFrame(), {}
    
    for path in latest_files:
        df, summary = parse_zip(path)
        if not df.empty:
            pair = df['pair'].iloc[0]
            if "BTC" in pair:
                btc_df, btc_sum = df, summary
            else:
                eth_df, eth_sum = df, summary
                
    if btc_df.empty or eth_df.empty:
        print("Error: Could not find valid BTC and ETH trade records.")
        return
        
    # 포트폴리오 시뮬레이션
    print("Simulating unified portfolio performance...")
    port_profit_pct, port_mdd, port_profit_abs = simulate_portfolio(btc_df, eth_df)
    
    # 결과 요약 JSON 파일 쓰기
    results_data = {
        "ratio_45": {
            "btc": {
                "profit": btc_sum.get("profit_total_pct", 0),
                "profit_abs": btc_sum.get("profit_total_abs", 0),
                "mdd": btc_sum.get("max_drawdown_account", 0) * 100,
                "trades": len(btc_df),
                "winrate": btc_sum.get("winrate", 0) * 100,
                "sharpe": btc_sum.get("sharpe", 0)
            },
            "eth": {
                "profit": eth_sum.get("profit_total_pct", 0),
                "profit_abs": eth_sum.get("profit_total_abs", 0),
                "mdd": eth_sum.get("max_drawdown_account", 0) * 100,
                "trades": len(eth_df),
                "winrate": eth_sum.get("winrate", 0) * 100,
                "sharpe": eth_sum.get("sharpe", 0)
            },
            "portfolio": {
                "profit": port_profit_pct,
                "profit_abs": port_profit_abs,
                "mdd": port_mdd,
                "trades": len(btc_df) + len(eth_df)
            }
        }
    }
    
    output_path = os.path.join(OUTPUT_DIR, "ratio_45_stats.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=4)
        
    print(f"Results successfully saved to {output_path}")
    print("Execution completed.")

if __name__ == "__main__":
    main()
