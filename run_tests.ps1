$ErrorActionPreference = "Stop"

echo "Running Solution 1 (Linear DCA)..."
Copy-Item "user_data\strategies\temp_sol1.py" "user_data\strategies\FreqaiMacroRegimeStrategy.py" -Force
freqtrade backtesting --strategy FreqaiMacroRegimeStrategy --config config.json --config config_freqai.json --freqaimodel LightGBMRegressor --timerange 20250510-20260510 > sol1_out.txt 2>&1
echo "Solution 1 Done."

echo "Running Solution 2 (1.0% Target)..."
Copy-Item "user_data\strategies\temp_sol2.py" "user_data\strategies\FreqaiMacroRegimeStrategy.py" -Force
freqtrade backtesting --strategy FreqaiMacroRegimeStrategy --config config.json --config config_freqai.json --freqaimodel LightGBMRegressor --timerange 20250510-20260510 > sol2_out.txt 2>&1
echo "Solution 2 Done."

echo "Running Solution 3 (-10% Stoploss)..."
Copy-Item "user_data\strategies\temp_sol3.py" "user_data\strategies\FreqaiMacroRegimeStrategy.py" -Force
freqtrade backtesting --strategy FreqaiMacroRegimeStrategy --config config.json --config config_freqai.json --freqaimodel LightGBMRegressor --timerange 20250510-20260510 > sol3_out.txt 2>&1
echo "Solution 3 Done."
