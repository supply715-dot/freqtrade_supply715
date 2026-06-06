$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "=== Running Final Optimized 4-Year BTC 72h Backtest ==="
C:\python_3_13_3_win64\Scripts\freqtrade.exe backtesting `
    --strategy V10_BTC_ETH_optimized `
    --config config_bt_btc.json `
    --config config_freqai_bt_btc_72h.json `
    --timerange 20220601-20260601 `
    --freqaimodel LightGBMRegressor

Write-Host "=== Running Final Optimized 4-Year ETH 24h Backtest ==="
C:\python_3_13_3_win64\Scripts\freqtrade.exe backtesting `
    --strategy V10_BTC_ETH_optimized `
    --config config_bt_eth.json `
    --config config_freqai_bt_eth_24h.json `
    --timerange 20220601-20260601 `
    --freqaimodel LightGBMRegressor

Write-Host "=== Final Optimized Backtests Completed Successfully ==="
