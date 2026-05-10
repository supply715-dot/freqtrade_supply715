# backtest_engine.py
import pandas as pd
from typing import Dict, Any

class PositionManager:
    """
    1. 트랜잭션 기록 및 포지션 관리 로직 담당.
    현재 자본금, 보유 포지션 상태(진입/청산), 거래 내역을 추적합니다.
    """
    def __init__(self, initial_capital: float, transaction_cost: float = 0.001):
        self.capital = initial_capital
        self.position = None  # 'LONG', 'SHORT', None
        self.entry_price = 0.0
        self.transaction_cost = transaction_cost
        self.trades = [] # (timestamp, type, price, size, pnl)

    def execute_trade(self, timestamp: pd.Timestamp, signal: str, current_price: float, data: pd.Series):
        """시그널에 따라 포지션을 진입하거나 청산합니다."""
        # NOTE: 실제 구현에서는 보유 수량(size)을 관리해야 합니다. 여기서는 1000으로 가정합니다.
        SIZE = 1000
        
        if signal == 'BUY' and self.position is None:
            cost = SIZE * current_price + self.transaction_cost
            self.capital -= cost
            self.position = 'LONG'
            self.entry_price = current_price
            self.trades.append((timestamp, 'ENTRY', current_price, SIZE, 0))
            print(f"[{timestamp}] -> LONG 진입 완료. 가격: {current_price:.4f}. 잔액: {self.capital:.2f}")
        
        elif signal == 'SELL' and self.position is not None:
            # 청산 로직
            exit_revenue = SIZE * current_price - self.transaction_cost
            pnl = exit_revenue - (self.entry_price * SIZE) # 단순 PnL 계산
            self.capital += exit_revenue
            self.position = None
            self.trades.append((timestamp, 'EXIT', current_price, SIZE, pnl))
            print(f"[{timestamp}] <- 청산 완료. 가격: {current_price:.4f}. PnL: {pnl:.2f}")

        # 포지션 보유 시 자본 변화는 calculate_equity에서 처리합니다.


    def calculate_equity(self, current_price: float) -> float:
        """현재 포지션을 기준으로 총 자산 가치(Equity)를 계산합니다."""
        if self.position == 'LONG':
            # 현재 자본금 + (보유 수량 * 현재가)
            return self.capital + 1000 * current_price
        else:
            return self.capital

class BacktestEngine:
    """
    2 & 3. 백테스트 실행 루프 및 KPI 계산을 담당하는 메인 엔진 클래스입니다.
    """
    def __init__(self, initial_capital: float, position_manager: PositionManager):
        self.position_manager = position_manager
        self.history = [] # 모든 시간 단계의 자산 가치 기록 (KPI 계산용)

    def generate_signal(self, row: pd.Series) -> str:
        """
        가상의 시그널 생성 로직 (실제로는 전략 모듈이 담당).
        여기서는 Feature A와 B를 활용합니다.
        """
        # 예시 전략: FeatureA가 임계값(0.5) 이상이고, FeatureB가 상승세일 때 매수 신호 발생 가정
        if row['Feature_A'] > 0.5 and row['Feature_B'] >= (row['Feature_B'].shift(1) * 1.1): # 10% 이상 증가 시
            return 'BUY' # 매수 시그널
        # 예시 전략: Feature A가 임계값(0.2) 이하일 때 청산 신호 발생 가정
        elif row['Feature_A'] < 0.2 and self.position_manager.position is not None:
            return 'SELL' # 매도/청산 시그널
        else:
            return 'HOLD'

    def run_backtest(self, data: pd.DataFrame):
        """데이터프레임 전체를 순회하며 백테스트를 실행합니다."""
        print("\n===============================================")
        print("🚀 Backtesting Engine 실행 시작...")
        for index, row in data.iterrows():
            timestamp = index # 인덱스를 시간으로 사용
            current_price = row['Close']

            # 1. 시그널 생성 (데이터와 현재 포지션 상태 기반)
            signal = self.generate_signal(row)

            # 2. 포지션 및 트랜잭션 업데이트
            self.position_manager.execute_trade(timestamp, signal, current_price, row)

            # 3. 자산 가치 기록 (KPI 계산에 필수)
            equity = self.position_manager.calculate_equity(current_price)
            self.history.append({'Timestamp': timestamp, 'Equity': equity})


    def calculate_kpis(self) -> Dict[str, float]:
        """
        최종 자산 기록을 기반으로 모든 핵심 성과 지표 (KPI)를 계산합니다.
        Business Agent가 정의한 5가지 KPI를 구현하는 핵심 부분입니다.
        """
        if not self.history:
            return {"Error": "백테스트 실행 이력이 없습니다."}

        df_equity = pd.DataFrame(self.history).set_index('Timestamp')
        
        # 시작 및 종료 자본금 정의
        initial_capital = df_equity['Equity'].iloc[0]
        final_capital = df_equity['Equity'].iloc[-1]
        total_return = (final_capital - initial_capital) / initial_capital * 100

        print("\n===============================================")
        print(f"📈 백테스트 완료. 최종 자본금: {final_capital:.2f} ({total_return:.2f}% 수익)")

        # KPI 계산 (구조 정의)
        kpis = {}
        kpis['Total Return (%)'] = total_return
        kpis['Sharpe Ratio'] = "<<Pandas-ta 등 라이브러리를 사용하여 표준화된 방식으로 구현 필요>>"
        kpis['Max Drawdown (%)'] = "<<최고점에서 최저점까지의 하락률을 추적해야 합니다>>"
        kpis['Win Rate (%)'] = f"{len([t for t in self.position_manager.trades if t[1] == 'ENTRY']) * 0.5:.2f}% (가상)" # 예시: 진입(BUY) 거래의 절반만 승리 가정
        kpis['Profit Factor'] = "<<총 이익/총 손실을 계산해야 합니다>>"

        return kpis


# --- 실행 테스트 코드 ---
if __name__ == "__main__":
    # 1. Mock 데이터 생성 (Orchestrator의 출력을 시뮬레이션)
    data = {
        'Open': [100, 102, 98, 105, 110],
        'High': [103, 104, 100, 107, 112],
        'Low': [99, 101, 97, 104, 108],
        'Close': [102, 103, 105, 109, 110],
        'Volume': [1e6] * 5,
        # Feature_A: 시장 심리 지수 (MSI) 시뮬레이션
        'Feature_A': [0.1, 0.7, 0.4, 0.2, 0.3],
        # Feature_B: 온체인 자본 흐름 (OCF) 시뮬레이션
        'Feature_B': [0.5, 0.6, 0.4, 0.1, 0.2]
    }
    dates = pd.to_datetime(['2026-05-09', '2026-05-10', '2026-05-11', '2026-05-12', '2026-05-13'])
    mock_data = pd.DataFrame(data, index=dates)

    # 2. 엔진 초기화 및 실행
    initial_capital = 10000.0  # 초기 자본금 설정
    pos_manager = PositionManager(initial_capital=initial_capital)
    engine = BacktestEngine(initial_capital, pos_manager)

    # 백테스트 실행
    engine.run_backtest(mock_data)

    # KPI 계산 및 출력
    final_kpis = engine.calculate_kpis()
    print("\n======================== 최종 KPI 요약 ========================")
    for k, v in final_kpis.items():
        print(f"-> {k}: {v}")