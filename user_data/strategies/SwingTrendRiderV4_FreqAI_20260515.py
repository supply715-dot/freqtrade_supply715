import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
from datetime import datetime, timedelta
from freqtrade.persistence import Trade

class SwingTrendRiderV4_FreqAI_20260515(IStrategy):
    INTERFACE_VERSION = 3

    # 전략 설정
    can_short: bool = True
    timeframe = '4h'
    
    # FreqAI 관련 설정
    process_only_new_candles = True
    use_exit_signal = True
    
    # ROI: AI가 관리하므로 더 유연하게 설정
    minimal_roi = {
        "0": 0.40,
        "480": 0.20,
        "960": 0.10
    }

    stoploss = -0.08 # AI 필터가 있으므로 약간 더 타이트하게

    # 트레일링 스탑
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    # -------------------------------------------------------------------------
    # FreqAI: 피처 엔지니어링 (학습 데이터 생성)
    # -------------------------------------------------------------------------
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        # 이평선
        dataframe[f"%-ema_{period}"] = ta.EMA(dataframe, timeperiod=period)
        # RSI
        dataframe[f"%-rsi_{period}"] = ta.RSI(dataframe, timeperiod=period)
        # MACD
        macd = ta.MACD(dataframe)
        dataframe[f"%-macd_{period}"] = macd['macd']
        dataframe[f"%-macdhist_{period}"] = macd['macdhist']
        # 변동성
        dataframe[f"%-atr_{period}"] = ta.ATR(dataframe, timeperiod=period)
        # 가격 모멘텀
        dataframe[f"%-pct_change_{period}"] = dataframe['close'].pct_change(period)
        
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        # 예측 목표: 향후 6봉(24시간) 동안의 수익률
        dataframe["&-target_roi"] = (
            dataframe["close"].shift(-6) / dataframe["close"] - 1
        )
        return dataframe

    # -------------------------------------------------------------------------
    # 지표 및 신호
    # -------------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 예측 수행 (이 메서드 안에서 모델 학습 및 예측이 일어남)
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 기본 스윙 지표 (V3 기반)
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=24)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # AI 예측 수익률 임계값
        # 5배 레버리지이므로 2.0% 이상의 상승을 예측할 때만 진입 (더 보수적으로 변경)
        ai_long_threshold = 0.02
        ai_short_threshold = -0.02
        
        # DI_ratio 필터: AI가 처음 보는 시장 데이터면 0.9 이하로 떨어짐
        di_limit = 0.9
        
        # 컬럼 존재 여부 확인 (오류 방지)
        if 'DI_ratio' not in dataframe.columns:
            dataframe['DI_ratio'] = 1.0
        if 'do_predict' not in dataframe.columns:
            dataframe['do_predict'] = 0

        # Long Entry: V3 추세 + AI 수익률 예측 + 데이터 신뢰도
        dataframe.loc[
            (dataframe['do_predict'] == 1) &           # AI 예측 활성화
            (dataframe['DI_ratio'] > di_limit) &       # 데이터 신뢰도 확보
            (dataframe['&-target_roi'] > ai_long_threshold) & # AI가 상승 예측
            (dataframe['fastEMA'] > dataframe['slowEMA']) &   # 골든크로스
            (dataframe['rsi'] > 55) &                  # RSI 필터 강화
            (dataframe['adx'] > 25),                   # ADX 필터 강화
            'enter_long'] = 1

        # Short Entry
        dataframe.loc[
            (dataframe['do_predict'] == 1) &
            (dataframe['DI_ratio'] > di_limit) &
            (dataframe['&-target_roi'] < ai_short_threshold) &
            (dataframe['fastEMA'] < dataframe['slowEMA']) &
            (dataframe['rsi'] < 45) &
            (dataframe['adx'] > 25),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # AI가 하락을 강력하게 예측하거나 추세가 꺾이면 탈출
        dataframe.loc[
            (dataframe['&-target_roi'] < 0) | 
            (dataframe['fastEMA'] < dataframe['slowEMA']),
            'exit_long'] = 1

        dataframe.loc[
            (dataframe['&-target_roi'] > 0) |
            (dataframe['fastEMA'] > dataframe['slowEMA']),
            'exit_short'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        # AI 모델이 판단한 손절가 사용 (여기서는 V3의 ATR 방식 유지하되 더 보수적으로)
        return -0.07 # 일관된 -7% 하드 손절

