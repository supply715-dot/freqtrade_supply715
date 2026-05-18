# 🚀 조나탄 AI 트레이딩: Freqtrade 실제 실행 및 운영 설명서 (CLI Execution Manual)

본 설명서는 **SwingTrendRiderV4_FreqAI_Active_20260515** 전략을 비롯한 Freqtrade 시스템을 윈도우 환경에서 실제로 기동하고, 과거 데이터를 구축하여 AI 모델을 학습 및 검증하고, 나아가 실거래(Paper/Live) 모드로 안전하게 배포하기 위한 **단계별 명령어 및 운영 가이드라인**입니다.

이 문서는 먼저 작성된 [WebUI 설치 및 사용법 가이드](file:///c:/Users/7supp/.gemini/antigravity/260509_freqtrade/manual/webui_manual_ko.md)와 긴밀하게 연동되어 완벽한 수동 및 자동 트레이딩 인프라 제어를 가능케 합니다.

---

## 📌 목차 (Table of Contents)
1. [⚙️ 1. 개발 환경 초기 셋업 및 가상환경 활성화](#%EF%B8%8F-1-%EA%B0%9C%EB%B0%9C-%ED%99%98%EA%B2%BD-%EC%B2%8A%EC%97%85-%EB%B0%8F-%EA%B0%8A%EC%83%81%ED%99%98%EA%B2%BD-%ED%99%9C%EC%84%B1%ED%99%94)
2. [📥 2. 과거 캔들 데이터 다운로드 (Data Downloading)](#-2-%EA%B3%BC%EA%B1%B0-%EC%BA%94%EB%93%A4-%EB%8D%B0%EC%9D%B4%ED%84%B0-%EB%8B%A4%EC%9A%B4%EB%A1%9C%EB%93%9C-data-downloading)
3. [🧠 3. FreqAI 모델 학습 및 백테스팅 (Backtesting with ML)](#-3-freqai-%EB%AA%A8%EB%8D%B8-%ED%95%99%EC%8A%B5-%EB%B0%8F-%EB%B0%B1%ED%85%8C%EC%8A%A4%ED%8C%85-backtesting-with-ml)
4. [📈 4. 하이퍼옵트(Hyperopt) 파라미터 최적화](#-4-%ED%95%98%EC%9D%B4%ED%8D%BC%EC%98%B5%ED%8A%B8hyperopt-%ED%8C%8C%EB%9D%BC%EB%AF%B8%ED%84%B0-%EC%B5%9C%EC%A0%81%ED%99%94)
5. [🤖 5. 가상 거래(Dry-run) 및 실거래(Live-run) 실행](#-5-%EA%B0%8A%EC%83%81-%EA%B1%B0%EB%9E%98dry-run-%EB%B0%8F-%EC%8B%A4%EA%B1%B0%EB%9E%98live-run-%EC%8B%A4%ED%96%89)
6. [🛠️ 6. 유용한 운영 꿀팁 및 문제 해결 (Troubleshooting)](#%EF%B8%8F-6-%EC%9C%A0%EC%9A%A9%ED%95%9C-%EC%9A%B4%EC%98%81-%EA%BF%80%ED%8C%81-%EB%B0%8F-%EB%AC%B8%EC%A0%9C-%ED%95%B4%EA%B2%B0-troubleshooting)

---

## ⚙️ 1. 개발 환경 셋업 및 가상환경 활성화

Freqtrade 및 FreqAI 패키지를 구동하기 위해서는 먼저 격리된 파이썬 가상환경을 활성화해야 모듈 충돌 및 경로 누수를 막을 수 있습니다.

### ① 자동 셋업 스크립트 실행 (최초 1회 또는 패키지 업데이트 시)
워크스페이스 루트 디렉토리에 정의된 [setup.ps1](file:///c:/Users/7supp/.gemini/antigravity/260509_freqtrade/setup.ps1) 스크립트를 사용하여 가상환경 생성 및 머신러닝(FreqAI) 핵심 의존성을 즉시 설치할 수 있습니다.

PowerShell을 실행하고 다음 명령을 순서대로 진행합니다:
```powershell
# 스크립트 실행 규칙 완화 (가동 오류 방지)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# setup.ps1 실행
.\setup.ps1
```
* **Tip**: 실행 중 표시되는 요구사항 메뉴에서 `requirements.txt`, `requirements-freqai.txt` 등을 방향키와 스페이스바(또는 쉼표 분리 문자)로 지정해 필요한 AI 라이브러리를 모두 활성화하십시오.

### ② 가상환경 수동 활성화
설치가 완료된 상태에서 새로운 PowerShell 창을 열어 작업을 진행할 때는 아래 명령어로 가상환경을 매번 **수동 활성화**해 주어야 합니다.
```powershell
# 가상환경 활성화 스크립트 실행
.venv\Scripts\Activate.ps1
```
* **성공 확인**: 터미널 프롬프트 가장 왼쪽에 `(.venv)` 표시가 나타나면 완벽히 진입한 것입니다.

---

## 📥 2. 과거 캔들 데이터 다운로드 (Data Downloading)

FreqAI 모델을 정밀하게 학습하고 백테스팅 결과를 정확히 확인하기 위해서는, 시뮬레이션할 과거 거래소 데이터를 로컬 하드디스크에 완벽하게 구축해 두어야 합니다.

> [!IMPORTANT]
> **5배 고레버리지 선물 전략 가동 시 주의사항**
> 선물(Futures) 모드의 백테스팅을 돌리기 위해서는 단순 현물 데이터가 아닌 **선물(Futures)용 무기한 스왑(Perpetual Swap) 데이터**를 다운로드 받아야 수수료 및 진입/청산 로직의 차이가 나지 않습니다.

### ① Binance 선물 4시간(4h) 데이터 다운로드 (권장)
* **다운로드 대상 페어**: BTC/USDT, ETH/USDT 선물
* **타임프레임**: 4h (모델 기본 주기)
* **다운로드 기간**: 최근 2년치 (예: 2024년 1월 1일 ~ 2026년 5월 1일)

```powershell
# Binance 선물 4h 캔들 데이터 구축
freqtrade download-data --exchange binance -t 4h --timerange 20240101-20260501 -p BTC/USDT:USDT ETH/USDT:USDT --trading-mode futures
```

### ② 다중 타임프레임 데이터 동시 구축
만약 전략 내부에서 다른 보조 지표 검증을 위해 1시간(1h)이나 15분(15m) 등 다중 주기 데이터를 함께 참조한다면, 다음과 같이 콤마(`,`)로 구분하여 동시에 한 번에 다운로드받으십시오:
```powershell
# 다중 타임프레임 동시 다운로드
freqtrade download-data --exchange binance -t 1h 4h --timerange 20240101-20260501 -p BTC/USDT:USDT ETH/USDT:USDT --trading-mode futures
```

---

## 🧠 3. FreqAI 모델 학습 및 백테스팅 (Backtesting with ML)

과거 데이터 다운로드가 완료되었다면, FreqAI에 탑재된 머신러닝 엔진(LightGBM)에게 과거 데이터를 공급하여 학습을 수행하고 그 예측 점수를 기반으로 한 백테스팅을 진행합니다.

> [!NOTE]
> FreqAI 기반 전략의 백테스팅은 최초 실행 시 **모델 학습 단계가 포함**되므로 하드웨어 스펙에 따라 5분 ~ 수십 분의 연산 시간이 다소 필요할 수 있습니다.

### ① FreqAI 액티브 선물 전략 백테스팅 기본 명령어
* **전략명**: `SwingTrendRiderV4_FreqAI_Active_20260515`
* **모델**: `LightGBMRegressor`
* **설정 파일**: 거래소/자본 기초 설정인 `config_bt.json`과 AI 연산 파라미터가 적힌 `config_freqai.json`을 **다중 설정(`--config`)**으로 병합해 투입합니다.

```powershell
# AI 선물 백테스팅 가동
freqtrade backtesting --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --config config_bt.json --config config_freqai.json --timerange 20250101-20260501 --freqaimodel LightGBMRegressor
```

### ② 이전 모델 학습 이력을 지우고 완전히 새로 학습시킬 때 (Purge Model)
이전에 진행한 AI 모델 캐시 파일들이 학습 연산에 얽혀 결과 왜겁을 방지하기 위해, FreqAI 파라미터를 크게 수정했을 때는 폴더를 비우거나 다음 명령을 적용해 신규 훈련을 유도합니다:
```powershell
# 모델 저장 디렉토리(user_data/models)의 특정 식별자 모델을 완전히 초기화하고 백테스트
freqtrade backtesting --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --config config_bt.json --config config_freqai.json --timerange 20250101-20260501 --freqaimodel LightGBMRegressor --freqai-purge
```

---

## 📈 4. 하이퍼옵트(Hyperopt) 파라미터 최적화

전략이 사용하는 고정된 하드웨어 스탑로스값(-8%)이나 캔들 이평선 주기, 혹은 익절 폭을 AI 알고리즘(Bayesian Search)을 동원해 수학적으로 가장 완벽한 성과를 내는 궁극의 값으로 튜닝해 주는 파라미터 최적화 기능입니다.

### ① 하이퍼옵트 가동 명령어
* **목표 공간 (Spaces)**: `roi` (수익 청산 영역) 및 `stoploss` (손절 제한 영역)
* **목표 에포크 (Epochs)**: `100`회 반복 탐색
* **평가 지표 (Loss)**: `CalmarHyperOptLoss` (겪는 MDD 하락 고통 대비 연성장률 비율을 가장 극대화하는 손실 평가식 적용)

```powershell
# 스탑로스 및 청산 타겟 최적화 가동
freqtrade hyperopt --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --config config_bt.json --config config_freqai.json --hyperopt-loss CalmarHyperOptLoss --spaces roi stoploss -e 100 --timerange 20250101-20260501
```

> [!TIP]
> **🚀 하이퍼옵트 연산 가속화 멀티코어 팁**
> 윈도우 CPU 코어 전체를 균등 활용하기 위해 `--jobs` 옵션을 지원하는 환경이거나 CPU 쓰레드가 여유 있다면 다음과 같이 작업 속도를 배가할 수 있습니다:
> `--jobs -1` 또는 `--jobs 8` (사용할 논리 프로세서 개수 강제 할당)

---

## 🤖 5. 가상 거래(Dry-run) 및 실거래(Live-run) 실행

백테스팅으로 모든 리스크 방어 가드와 AI의 유효성이 검증되었다면, 이제 실시간 시세 호가창에 연동하여 봇을 영구히 기동시키는 2단계 핵심 운영 실행 단계입니다.

### ① 가상 거래 (Dry-run, 모의 투자) 구동
* 실제 돈을 소모하지 않고, 실시간으로 거래소 시세판을 모니터링하며 AI 진입/청산 신호가 맞는지 시뮬레이션 지갑에 체결 처리합니다.
* **설정 파일**: [config.json](file:///c:/Users/7supp/.gemini/antigravity/260509_freqtrade/config.json)

```powershell
# 가상 실거래 무중단 상태 대기 구동
freqtrade trade --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --freqaimodel LightGBMRegressor --config config.json --dry-run
```
* **모니터링**: 봇이 켜진 채로 유지된다면 웹 브라우저에서 `http://127.0.0.1:8080`에 즉시 접속할 수 있습니다.

### ② 실거래 (Live-run, 실전 투자) 구동
가상 거래의 안정성이 확보되어 실제 시드를 5배 레버리지로 운용할 때 적용합니다.

1. **사전 준비**: [config.json](file:///c:/Users/7supp/.gemini/antigravity/260509_freqtrade/config.json)의 `"dry_run"` 옵션을 `false`로 수정하고, `exchange` 섹션의 `"key"`와 `"secret"`에 거래소(Bybit 등) API 키 값을 비밀번호와 함께 안전하게 명시합니다. (혹은 별도의 `secrets.json` 파일을 분리 연동)
2. **실행 명령어**:
```powershell
# 실제 현금 운용 실전 라이브 기동
freqtrade trade --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --freqaimodel LightGBMRegressor --config config.json
```

> [!WARNING]
> **🚨 실거래 기동 시 중대 경고**
> 1. 실거래 시에는 반드시 **레버리지(Leverage)**가 거래소 홈페이지 상에 설정된 배수와 봇이 설정한 배수가 일치하는지 먼저 확인하십시오.
> 2. 가용 자산의 전부를 잃지 않도록 `config.json`의 `max_open_trades`를 가급적 `2`~`3` 정도로 작게 분산 통제하고, `stake_amount` 단위를 적절히 제한하십시오.

---

## 🛠️ 6. 유용한 운영 꿀팁 및 문제 해결 (Troubleshooting)

### ① 가상 실거래 거래 장부 완전 초기화 (Reset Database)
봇을 껐다 켜거나 전략을 튜닝하는 과정에서 모의 투자 누적 거래 기록 데이터베이스(`tradesv3.dryrun.sqlite`)가 오염되어 누적 수익률 계산이 왜곡된다면, 다음 명령어로 가볍게 DB를 날려 새롭게 0달러부터 다시 카운팅할 수 있습니다.
```powershell
# PowerShell 경로에서 가상 DB 삭제
Remove-Item tradesv3.dryrun.sqlite -ErrorAction SilentlyContinue
```
* **주의**: 봇이 구동되는 도중에는 데이터베이스 파일이 잠겨 있어 삭제가 불가능하므로, **반드시 봇 프로세스를 정지(Ctrl + C)한 뒤에 삭제**해 주십시오.

### ② OOM (Out Of Memory) 및 CPU 폭주 오류 해결
FreqAI는 대용량 머신러닝 연산을 윈도우 CPU 멀티쓰레드를 풀가동하여 진행하기 때문에 저사양 PC나 노트북에서는 윈도우가 먹통이 되거나 튕길 수 있습니다.

* **해결 조치 1**: `config.json`의 `freqai.data_kitchen.thread_count` 값을 시스템 성능에 맞춰 제한하십시오:
  ```json
  "data_kitchen": {
      "thread_count": 4  // 기본 8에서 4 또는 2로 하향 조절하여 CPU 부하 경감
  }
  ```
* **해결 조치 2**: 윈도우 **가상 메모리(페이징 파일 크기)**를 C드라이브 기준 `16GB` 이상으로 넉넉하게 확장하면 대단위 데이터 백테스트 시 발생하는 프로그램 강제 종료 오류를 미연에 원천 봉쇄할 수 있습니다.

---
*본 가이드는 조나탄 AI 트레이딩 시스템 전용 매뉴얼 폴더 내에 안전하게 아카이브되어 영구히 보존됩니다.*
