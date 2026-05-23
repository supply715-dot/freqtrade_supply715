# AI 기반 7배 레버리지 스윙 전략 운영 매뉴얼 (CLI Execution Manual)

본 매뉴얼은 최종 채택된 **`SwingTrendRiderV4_FreqAI_Active_20260515`** 전략을 Freqtrade 가상 거래(Dry-run) 및 실거래(Live-run) 환경에서 가동하고, 백테스트 및 모델 재학습을 안정적으로 운영하기 위한 한글 가이드라인입니다.

---

## 목차 (Table of Contents)
1. [1단계: 개발 환경 셋업 및 가상환경 활성화](#1단계-개발-환경-셋업-및-가상환경-활성화)
2. [2단계: 과거 캔들 데이터 다운로드 (최근 3개년 4H 단일)](#2단계-과거-캔들-데이터-다운로드-최근-3개년-4h-단일)
3. [3단계: FreqAI 모델 학습 및 백테스트 실행](#3단계-freqai-모델-학습-및-백테스트-실행)
4. [4단계: 하이퍼옵트(Hyperopt) 파라미터 최적화](#4단계-하이퍼옵트hyperopt-파라미터-최적화)
5. [5단계: 가상 거래(Dry-run) 및 실거래(Live-run) 가동](#5단계-가상-거래dry-run-및-실거래live-run-가동)
6. [6단계: 문제 해결 및 최적화 꿀팁 (OOM 방지)](#6단계-문제-해결-및-최적화-꿀팁-oom-방지)

---

## 1단계: 개발 환경 셋업 및 가상환경 활성화

Freqtrade와 FreqAI 머신러닝 모듈을 안정적으로 가동하기 위해서는 반드시 파이썬 가상환경을 활성화해야 합니다.

### ① 의존성 설치 (필요시 최초 1회 실행)
파워쉘(PowerShell) 콘솔을 열고 가상환경 의존성을 동기화합니다.
```powershell
# 스크립트 실행 권한 부여
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# setup.ps1 실행
.\setup.ps1
```
* **참고**: 실행 메뉴에서 FreqAI 패키지(`requirements-freqai.txt`) 가 활성화되어 관련 AI 라이브러리(LightGBM, Scikit-learn 등)가 올바르게 설치되었는지 확인합니다.

### ② 가상환경 활성화
서버 가동이나 명령을 실행하기 전, 매번 아래 명령을 파워쉘에 실행하여 가상환경 콘솔에 진입합니다.
```powershell
.venv\Scripts\Activate.ps1
```
* **활성화 확인**: 콘솔 경로 맨 왼쪽에 `(.venv)` 표시가 보이면 정상적으로 활성화된 상태입니다.

---

## 2단계: 과거 캔들 데이터 다운로드 (최근 3개년 4H 단일)

FreqAI 모델 학습 및 백테스트를 실행하기 위한 선물 과거 데이터를 다운로드합니다.

> [!IMPORTANT]
> **타임프레임 및 기간 가이드**
> - **타임프레임**: 최종 전략인 V4 Active는 **`4h`** 단일 타임프레임만 주력으로 활용합니다. 1시간(1h) 데이터는 학습 연산량 과부하(OOM) 방지와 가짜 돌파(휩소) 차단을 위해 최종 버전에서 제외되었으므로, 불필요하게 1h 데이터를 다운로드할 필요가 없습니다.
> - **다운로드 기간**: 최근 3개년(`2023-05-23` ~ `2026-05-23`) 선물 시장 데이터를 기준으로 다운로드합니다.

### ① 바이낸스 선물 거래소 4시간(4h) 데이터 다운로드
```powershell
freqtrade download-data --exchange binance -t 4h --timerange 20230523-20260523 -p BTC/USDT:USDT ETH/USDT:USDT --trading-mode futures
```
* **참고**: 선물 거래를 모사하기 위해 `--trading-mode futures` 옵션이 필수적으로 지정되어야 하며, 백테스트 엔진이 거래소의 mark 캔들과 funding_rate 캔들을 자동으로 함께 매칭해 다운로드하게 됩니다.

---

## 3단계: FreqAI 모델 학습 및 백테스트 실행

다운로드한 최근 3개년 데이터를 기반으로 FreqAI 머신러닝(LightGBM) 모델을 학습하고 검증합니다.

> [!NOTE]
> FreqAI 백테스트는 기계학습 모델의 주기적인 재학습(Retrain)을 병행하므로, CPU 및 그래픽 환경에 따라 최소 5분에서 20분 이상 소요될 수 있습니다.

### ① FreqAI 백테스트 기본 명령어
```powershell
freqtrade backtesting --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --config config_bt.json --config config_freqai.json --timerange 20230523-20260523 --freqaimodel LightGBMRegressor
```
* **설정 연동**: 기본 백테스트 설정 파일(`config_bt.json`)과 머신러닝 파라미터 파일(`config_freqai.json`)을 다중 지정(`--config`)하여 연동합니다.

### ② 기존 학습 모델 초기화 후 백테스트 (`--freqai-purge`)
이전 학습 로그가 꼬이거나 완전 새로운 데이터셋으로 모델을 신규 학습하고자 할 때는 아래 옵션을 끝에 추가합니다.
```powershell
freqtrade backtesting --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --config config_bt.json --config config_freqai.json --timerange 20230523-20260523 --freqaimodel LightGBMRegressor --freqai-purge
```

---

## 4단계: 하이퍼옵트(Hyperopt) 파라미터 최적화

백테스트 성과 지표(Calmar Ratio, MDD)를 극대화하기 위해 전략 파라미터(RSI, ADX 진입 기준 및 ROI 타겟 등)를 탐색하고 최적화합니다.

```powershell
freqtrade hyperopt --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --config config_bt.json --config config_freqai.json --hyperopt-loss CalmarHyperOptLoss --spaces buy roi -e 100 --timerange 20230523-20260523
```
* **`-e 100`**: 최적화 최적값 도출을 위해 100회 탐색을 반복합니다.
* **`--spaces buy roi`**: 매수 기준 파라미터와 적정 ROI 테이블 공간을 탐색 공간으로 지정합니다.
* **`--jobs -1`**: 컴퓨터의 모든 CPU 코어를 사용하여 연산 속도를 극대화합니다.

---

## 5단계: 가상 거래(Dry-run) 및 실거래(Live-run) 가동

모델 검증이 끝나면 실제 시장 가격을 연동하여 가상 포지션을 운용하거나 실거래 봇을 구동합니다.

### ① 가상 거래 (Dry-run) 구동
계좌 자금을 쓰지 않고 바이비트(Bybit) 또는 바이낸스(Binance)의 실시간 시세를 추적하며 AI 진입/탈출 신호를 시뮬레이션합니다.
```powershell
freqtrade trade --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --freqaimodel LightGBMRegressor --config config.json --dry-run
```
* 봇 구동 후 로컬 브라우저 `http://127.0.0.1:8080`에 접속하여 FreqUI 웹 화면으로 AI 모니터링을 진행할 수 있습니다.

### ② 실거래 (Live-run) 구동
실제 투자금을 사용하여 바이비트 선물 계좌에서 무기한 선물을 거래합니다.

1. **설정 수정**: `config.json` (또는 `secrets.json`)에서 `"dry_run"` 옵션을 `false`로 수정하고, 거래소 API Key 및 Secret 정보를 입력합니다.
2. **실거래 명령어 실행**:
   ```powershell
   freqtrade trade --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --freqaimodel LightGBMRegressor --config config.json
   ```

> [!WARNING]
> **7배 레버리지 적용 및 선물 리스크 수칙**
> 1. **레버리지 기본값 설정**: 본 전략의 기본 레버리지는 7배(`opt_leverage = 7`)로 조율되어 작동합니다.
> 2. **강제 청산 방지 손절 제어**: 레버리지 7배 환경에서 `-20.6%` 등의 큰 손절 범위를 적용할 경우 자산의 100% 이상 손실로 거래소 강제 청산(Margin Cut)을 당하게 됩니다. 이에 따라 본 전략은 리스크를 방어하기 위한 안전 마진선으로 **손절선을 `-8.0%`(실질 자산 기준 -56% 손실선)로 코드 내부 고정 제어**하고 있습니다. 실거래 시 이를 자의적으로 넓히지 않도록 주의하십시오.
> 3. **동시 거래 수 제한**: 리스크 분산을 위해 `config.json`의 `"max_open_trades"`는 최대 **`2`** 또는 **`3`**으로 타이트하게 제한해 둘 것을 권장합니다.

---

## 6단계: 문제 해결 및 최적화 꿀팁 (OOM 방지)

### ① AI 학습 중 메모리 초과(OOM)로 봇이 튕길 때
FreqAI는 대량의 데이터 학습 시 메모리 사용량이 크게 급증합니다. PC 사양(예: RAM 16GB 이하)이 낮아 오류가 발생하면 아래 해결책을 조치합니다.
- **해결책 1 (스레드 조정)**: `config_freqai.json` 또는 `config.json` 내의 FreqAI 학습 스레드 수를 절반 이하로 줄입니다.
  ```json
  "data_kitchen": {
      "thread_count": 4  // 기본 8스레드에서 4 또는 2스레드로 낮추어 메모리 분배
  }
  ```
- **해결책 2 (가상 메모리 확장)**: 윈도우 설정에서 C드라이브의 **가상 메모리(페이징 파일 크기)**를 `16GB` 또는 `32GB` 이상으로 충분히 수동 확장하여 OOM 발생을 미연에 방지합니다.

### ② Dry-run 테스트 거래 기록 초기화 (DB Reset)
가상 거래 시 데이터베이스에 남은 이전 포지션이나 거래 이력을 삭제하고 0달러 상태에서 다시 테스트를 시작하려면 데이터베이스 파일을 삭제하십시오.
```powershell
# 봇 프로세스를 중지(Ctrl + C)한 뒤 실행
Remove-Item tradesv3.dryrun.sqlite -ErrorAction SilentlyContinue
```

---
*본 매뉴얼은 AI 기반의 7배 레버리지 스윙 트레이딩 전략에 맞게 지속적으로 업데이트되며, 추가 질문은 텔레그램 연동 봇 상태 창을 통해 모니터링이 가능합니다.*
