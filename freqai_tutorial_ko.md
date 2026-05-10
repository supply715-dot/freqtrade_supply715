# 🤖 FreqAI 초보자 가이드 및 튜토리얼 (한글 요약본)

## 1. FreqAI란 무엇인가요?
FreqAI는 Freqtrade 내부에 기본 탑재된 **머신러닝(기계학습) 알고리즘 모듈**입니다. 기존 봇이 "RSI가 30 이하일 때 매수"와 같은 정해진 수학적 규칙을 따랐다면, FreqAI는 **"과거 차트 패턴을 AI가 학습하여 미래의 가격 변동(상승/하락) 확률을 예측"**하고 그에 따라 매매를 결정합니다.

* **지원 모델**: LightGBM, CatBoost, XGBoost, Random Forest, PyTorch(딥러닝), 강화학습(RL) 등

---

## 2. FreqAI 동작의 3가지 핵심 요소

FreqAI를 이해하려면 다음 3가지 단어를 알아야 합니다.

1. **Features (특징점)**: AI에게 학습시킬 힌트들입니다. (예: "현재 RSI 수치", "볼린저 밴드 넓이", "최근 5봉간의 거래량 변화" 등)
2. **Targets (목표점)**: AI가 예측해야 할 정답입니다. (예: "앞으로 10분 뒤 가격이 지금보다 2% 오를 것인가?")
3. **Model (모델)**: 입력된 힌트(Features)와 정답(Targets)을 분석하여 패턴을 찾아내는 인공지능 뇌입니다. (예: LightGBM)

---

## 3. FreqAI 튜토리얼: LightGBM 모델 돌려보기

Freqtrade는 초보자를 위해 설정이 완료된 예제 파일(`freqai_example_strategy.py`)을 제공합니다. 이를 이용해 가장 빠른 머신러닝 모델 중 하나인 **LightGBM**을 학습시키는 방법입니다.

### 1단계: FreqAI 전용 라이브러리 설치
FreqAI는 무거운 수학 연산을 하므로 추가 라이브러리 설치가 필요합니다. 터미널에 아래 명령어를 입력하세요.
```bash
pip install -r requirements-freqai.txt
```

### 2단계: 과거 데이터 다운로드 (충분한 양 필요)
AI가 패턴을 찾려면 일반 백테스팅보다 훨씬 많은 과거 데이터가 필요합니다. 최소 1개월 이상의 데이터(권장: 3~6개월)를 받습니다.
```bash
freqtrade download-data --exchange binance --pairs BTC/USDT ETH/USDT --days 60 --timeframe 5m 15m
```

### 3단계: AI 학습 및 백테스팅 동시 실행
이제 예제 전략과 예제 설정 파일을 사용하여 AI를 학습시키고, 동시에 그 결과가 어땠는지 백테스팅을 진행합니다.
```bash
freqtrade backtesting --strategy FreqaiExampleStrategy --config config.json --config config_examples/config_freqai.example.json --timerange 20240101-20240201
```

> ⚠️ **주의**: 이 명령어를 실행하면 컴퓨터가 데이터를 분석하고 AI 모델을 만드느라 팬(Fan)이 세게 돌고 시간이 꽤 오래 걸릴 수 있습니다. (CPU 연산 집중)

---

## 4. 실행 후 일어나는 일

명령어를 실행하면 터미널에서 다음과 같은 일들이 순차적으로 일어납니다.

1. **데이터 스플릿(Data Split)**: 60일치 데이터를 가져와서, "공부할 데이터(Train)"와 "시험 볼 데이터(Test)"로 나눕니다.
2. **모델 학습(Training)**: `FreqaiExampleStrategy.py`에 정의된 지표(RSI, MACD 등)를 바탕으로 AI가 열심히 패턴을 외우고 공식을 만듭니다.
3. **추론 및 매매(Inferencing)**: 만들어진 AI 뇌를 시험 데이터에 적용하여 "여기서 사고, 저기서 팔아라"라고 명령을 내립니다.
4. **결과 출력**: 평소 백테스팅을 했을 때처럼 총수익률(Profit)과 최대 낙폭(Drawdown) 결과를 화면에 보여줍니다.

## 5. 다음 단계 (고급)
예제 전략이 돌아가는 것을 확인했다면, `user_data/strategies/freqai_example_strategy.py` 파일을 열어 `feature_engineering_*` 함수 안의 코드를 수정해 보세요. AI에게 어떤 보조지표를 힌트(Feature)로 줄 것인지 본인만의 아이디어를 추가하여 승률을 높일 수 있습니다.
