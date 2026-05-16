import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
from datetime import datetime, timedelta
from freqtrade.persistence import Trade

class SwingTrendRiderV4_FreqAI_Active_20260515(IStrategy):
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

    stoploss = -0.08 

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
        dataframe[f"%-ema_{period}"] = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-rsi_{period}"] = ta.RSI(dataframe, timeperiod=period)
        macd = ta.MACD(dataframe)
        dataframe[f"%-macd_{period}"] = macd['macd']
        dataframe[f"%-macdhist_{period}"] = macd['macdhist']
        dataframe[f"%-atr_{period}"] = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-pct_change_{period}"] = dataframe['close'].pct_change(period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["&-target_roi"] = (
            dataframe["close"].shift(-6) / dataframe["close"] - 1
        )
        return dataframe

    # -------------------------------------------------------------------------
    # 지표 및 신호
    # -------------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 예측 수행
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 기본 지표
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=24)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 공격적 세팅 (Active Mode) ---
        prediction_threshold = 0.012 # 2.0% -> 1.2% 로 하향
        adx_min = 20                 # 25 -> 20 으로 하향
        rsi_long = 52                # 55 -> 52 로 하향
        rsi_short = 48               # 45 -> 48 로 상향 (범위 확대)
        di_limit = 0.5               # 데이터 신뢰도 필터 (약간 완화)
        
        if 'DI_ratio' not in dataframe.columns:
            dataframe['DI_ratio'] = 0.0
        if 'do_predict' not in dataframe.columns:
            dataframe['do_predict'] = 0

        # Long Entry: AI 예측 + 추세 필터
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] > prediction_threshold) &
                (dataframe['rsi'] > rsi_long) &
                (dataframe['adx'] > adx_min) &
                (dataframe['tema'] > dataframe['ema200'])
            ),
            'enter_long'] = 1

        # Short Entry
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] < -prediction_threshold) &
                (dataframe['rsi'] < rsi_short) &
                (dataframe['adx'] > adx_min) &
                (dataframe['tema'] < dataframe['ema200'])
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 추세가 완전히 꺾이면 탈출
        dataframe.loc[
            (dataframe['fastEMA'] < dataframe['slowEMA']),
            'exit_long'] = 1

        dataframe.loc[
            (dataframe['fastEMA'] > dataframe['slowEMA']),
            'exit_short'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        return -0.08
