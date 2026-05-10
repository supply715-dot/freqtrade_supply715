# 🧪 Backtesting Risk Module Interface Specification

## 목적
개발자가 구현할 리스크 관리 모듈이 백테스팅 엔진의 핵심 트랜잭션 루프에 안정적으로 통합될 수 있도록, 입력(Input) 및 출력(Output) 사양을 명확히 정의합니다.

## 1. 필수 Input 데이터 구조 (Engine $\to$ Module)
모든 포지션 진입 결정 시점에 아래 데이터를 모듈로 전달해야 합니다.

| 변수명 | 타입 | 설명 | 예시 값 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| `current_ohlcv` | Dict/Tuple | 현재 봉의 OHLCV 데이터 (Timestamp, Open, High, Low, Close, Volume) | `{'t': ..., 'o': 100, ...}` | 필수 기본 입력 |
| `historical_features` | DataFrame | 직전 $N$ 기간의 모든 외부 Feature 값 (MSI, OCF 등) | pd.DataFrame[...] | ATR 계산에 활용될 데이터 |
| `capital_available` | Float | 현재 시점의 가용 자본금 ($) | 100,000.0 | 포지션 사이즈 제한 근거 |

## 2. 필수 Output 값 구조 (Module $\to$ Engine)
모듈은 트랜잭션을 실행할 수 있는 구체적인 매개변수(Parameter)를 반환해야 합니다.

| 변수명 | 타입 | 설명 | 예시 값 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| `max_position_size` | Float | 해당 시점에서 진입 가능한 최대 금액 (USD). ($1.5\%$ 제한 반영) | 1,500.0 | **(핵심)** |
| `stop_loss_level` | Float | 손절매가 도달해야 하는 가격 레벨 (Exit Price). | 98.5 | ATR 기반으로 계산되어야 함 |
| `take_profit_level` | Float | 이익 실현 목표에 도달해야 하는 가격 레벨 (Target Price). | 103.0 | R:R 비율을 반영하여 계산되어야 함 |

## 3. 로직 요구사항 재확인
*   **Position Sizing:** `max_position_size`는 항상 $\le \text{capital\_available} \times 0.015$여야 합니다.
*   **SL/TP Calculation:** SL 및 TP 레벨은 반드시 `historical_features`를 통해 계산된 **최신 ATR 값**을 기반으로 해야 합니다.