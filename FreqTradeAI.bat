@echo off
title FreqTradeAI Trading Bot
echo ===================================================
echo  FreqTradeAI Bot starting (Strategy: V8_BTC_ETH_optimized)
echo ===================================================
cd /d "c:\Users\7supp\.gemini\antigravity\260509_freqtrade"

:: WebUI 포트 대기 루프 (백신 우회를 위해 파워셸 대신 파이썬 socket 통신 사용)
echo Waiting for WebUI server to be ready...
start /b python -c "import socket, time, webbrowser; [time.sleep(1) for _ in range(60) if socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('127.0.0.1', 8080)) != 0]; webbrowser.open('http://localhost:8080')"

:: Freqtrade 실행
echo Running Freqtrade trading engine...
python -m freqtrade trade --strategy V8_BTC_ETH_optimized --config config.json --config secrets.json --config config_freqai.json --freqaimodel LightGBMRegressor

pause
