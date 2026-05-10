import logging
from typing import Dict, Any

import pandas as pd
import numpy as np
from pandas import DataFrame
import talib.abstract as ta
import pandas_ta as pta

from datetime import datetime
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_open

logger = logging.getLogger(__name__)

class FreqaiMacroRegimeStrategy(IStrategy):
    """
    Pine Script (Macro Regime Engine V18.4) -> FreqAI 변환 1차 코드
    복잡한 if/else 조건을 AI의 판단(Features)으로 전환한 버전입니다.
    """
    
    # 1. 기본 설정 (Freqtrade 환경)
    timeframe = '5m'
    startup_candle_count = 100
    
    # Pine Script의 고정 수익률 청산 (0분: 4%, 30분: 2%, 60분: 1%)
    minimal_roi = {
        "0": 0.04,
        "6": 0.02,   # 5분봉 기준 6봉 = 30분
        "12": 0.01   # 5분봉 기준 12봉 = 60분
    }
    
    # 10% 강제 청산 (Pine Script의 stoploss_pct)
    stoploss = -0.10

    process_only_new_candles = True
    use_exit_signal = True

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: Dict[str, Any], **kwargs) -> DataFrame:
        """
        [1. AI 학습용 데이터 (Features) 생성]
        Pine Script의 핵심 지표들을 AI가 학습할 수 있도록 제공합니다.
        FreqAI는 '%-' 로 시작하는 컬럼들을 자동으로 학습 힌트로 인식합니다.
        """
        # --- 1) Macro Regime 기반 지표 (Fast/Slow EMA, RSI, ADX) ---
        dataframe[f'%-ema_fast_{period}'] = ta.EMA(dataframe, timeperiod=5)
        dataframe[f'%-ema_slow_{period}'] = ta.EMA(dataframe, timeperiod=20)
        dataframe[f'%-rsi_macro_{period}'] = ta.RSI(dataframe, timeperiod=5)
        dataframe[f'%-adx_macro_{period}'] = ta.ADX(dataframe, timeperiod=7)
        
        # EMA 이격도 강도 (%)
        dataframe[f'%-ema_dist_pct_{period}'] = (
            (dataframe[f'%-ema_fast_{period}'] - dataframe[f'%-ema_slow_{period}']) / 
            dataframe[f'%-ema_slow_{period}'] * 100
        )

        # --- 2) HTF Market State 기반 (SMA 정렬도, 기울기) ---
        dataframe[f'%-sma_5_{period}'] = ta.SMA(dataframe, timeperiod=5)
        dataframe[f'%-sma_20_{period}'] = ta.SMA(dataframe, timeperiod=20)
        dataframe[f'%-sma_40_{period}'] = ta.SMA(dataframe, timeperiod=40)
        
        # 단기 SMA 기울기 (상승세/하락세 파악용)
        dataframe[f'%-sma_5_slope_{period}'] = dataframe[f'%-sma_5_{period}'] - dataframe[f'%-sma_5_{period}'].shift(1)
        dataframe[f'%-sma_20_slope_{period}'] = dataframe[f'%-sma_20_{period}'] - dataframe[f'%-sma_20_{period}'].shift(1)
        
        # --- 3) 변동성 (ATR) 및 볼린저 밴드 (BBW) ---
        dataframe[f'%-atr_{period}'] = ta.ATR(dataframe, timeperiod=14)
        dataframe[f'%-candle_range_{period}'] = dataframe['high'] - dataframe['low'] # 폭포수/로켓 감지용
        
        bbands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe[f'%-bb_middle_{period}'] = bbands['middleband']
        dataframe[f'%-bbw_{period}'] = (bbands['upperband'] - bbands['lowerband']) / bbands['middleband'] * 100
        
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        """
        [2. 거래량 및 심화 지표]
        CVD (Cumulative Volume Delta) 파인스크립트 모방 로직
        """
        # 양봉이면 거래량 매수(+), 음봉이면 거래량 매도(-) 로 치환하여 CVD 흐름 파악
        dataframe['vol_direction'] = 1
        dataframe.loc[dataframe['close'] < dataframe['open'], 'vol_direction'] = -1
        dataframe['%-pseudo_cvd'] = (dataframe['volume'] * dataframe['vol_direction']).rolling(window=10).sum()
        
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        """
        [3. 시간적 흐름 (Time Features)]
        AI가 "이 시간대에는 주로 하락하더라" 같은 패턴을 인지하도록 돕습니다.
        """
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        """
        [4. AI 예측 목표치 (Target)]
        우리가 AI에게 묻는 핵심 질문입니다. (예: "그래서 앞으로 오를까 내릴까?")
        """
        # 목표: 현재 지점으로부터 15캔들 뒤의 가격이 몇 퍼센트 변동했는지를 예측
        # '&s-' 로 시작하는 컬럼이 FreqAI의 예측 대상 정답지입니다.
        dataframe["&s-future_roi_15"] = (
            dataframe["close"].shift(-15) - dataframe["close"]
        ) / dataframe["close"]
        
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """ 보조지표 계산 및 FreqAI 실행 트리거 """
        # 위에서 정의한 Feature 함수들을 내부적으로 실행하여 AI 모델링 준비 완료
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # -------------------------------------------------------------
        # 아래는 AI 피처(학습 데이터)가 아니라, 실제 '청산 로직' 방어용 지표들입니다.
        # (V18.2 Stable ATR, RBB Lower 등) - 2단계 개발에서 활용될 예정
        # -------------------------------------------------------------
        dataframe['stable_atr'] = ta.ATR(dataframe, timeperiod=14).shift(3)
        
        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        [5. 매수 조건 (AI의 판단)]
        복잡한 if/else를 걷어내고, 오직 "AI가 충분히 오를 것이라 확신하는가?"만 물어봅니다.
        """
        enter_long = (
            (df['do_predict'] == 1) &  # AI 예측이 정상적으로 활성화되었고
            # AI 모델의 예측 결과(미래 15봉 수익률)가 0.8% 이상 오를 것이라고 베팅할 때!
            (df['do_predict_&s-future_roi_15'] > 0.008) 
        )
        
        df.loc[enter_long, ['enter_long', 'enter_tag']] = (1, 'freqai_macro_entry')
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        [6. 매도 조건 (AI의 판단)]
        """
        exit_long = (
            (df['do_predict'] == 1) &
            # AI 예측 결과가 -0.2% 밑으로 떨어질 것이라고 뷰(View)가 바뀌었을 때 손절/익절
            (df['do_predict_&s-future_roi_15'] < -0.002) 
        )
        
        df.loc[exit_long, ['exit_long', 'exit_tag']] = (1, 'freqai_macro_exit')
        return df

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        [커스텀 동적 손절 로직]
        잦은 손절(휩소)을 방지하기 위해 AI에게 넉넉한 유예기간을 주고 노이즈를 견딜 수 있게 합니다.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        atr = last_candle.get('stable_atr', 0)
        if atr == 0 or pd.isna(atr):
            return -0.15  # 기본 15% 하드스탑

        # 1. 넉넉한 하드스탑 (4.0 ATR) - 일반적인 노이즈 파동에 털리지 않도록 방어
        atr_pct = atr / trade.open_rate
        sl_pct = -(atr_pct * 4.0)

        # 2. 부드러운 Time-Decay (시간이 지나도 수익이 안 날 때만 조임)
        # 파인스크립트에서는 매우 공격적으로 조였으나, 여기서는 2시간 유예를 줍니다.
        trade_duration_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        if trade_duration_minutes > 120 and current_profit < 0.01:
            sl_pct = -(atr_pct * 2.0)

        # 오픈가 기준으로 손절 퍼센티지를 Freqtrade 규격에 맞게 변환하여 반환
        return stoploss_from_open(sl_pct, current_profit, is_short=trade.is_short)

    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs):
        """
        [커스텀 강제 청산 로직 (익절/탈출)]
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # 1. Fast Breakeven 완화 (조기 털림 방지)
        # 기존: 조금만 오르면 바로 본절로 올려서 노이즈에 털림.
        # 변경: 넉넉하게 3% 이상 상승했을 때만 수익 보존 모드로 전환
        if current_profit > 0.03:
            return "roi_breakeven_secured"

        # 2. AI 예측 뷰 악화 시 긴급 탈출 (State Direction Exit 대용)
        # AI 예측이 심각한 하락(-0.5% 이하)으로 바뀌었고, 현재 약수익/약손실 상태라면 굳이 버티지 않고 탈출
        predict_roi = last_candle.get('do_predict_&s-future_roi_15', 0)
        if current_profit > -0.01 and predict_roi < -0.005:
            return "ai_panic_exit"
            
        return None

