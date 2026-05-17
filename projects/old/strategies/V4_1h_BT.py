import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from datetime import datetime
from freqtrade.persistence import Trade

class V4_1h_BT(IStrategy):
    """
    [백테스트용] 1h 기반 informative 전략
    - 주 timeframe: 1h (4h보다 빠른 신호 감지)
    - 1h 추세 이탈 감지 + custom_stoploss로 조기 청산
    - 4h 전략 대비 진입 빈도 증가, 손절 타이트화
    """
    INTERFACE_VERSION = 3

    can_short: bool = True
    timeframe = '1h'           # 1h를 메인으로 사용
    startup_candle_count: int = 200

    process_only_new_candles = True
    use_exit_signal = True

    minimal_roi = {
        "0": 0.40,
        "120": 0.20,    # 4h 기준 480분 → 1h 기준 120분
        "240": 0.10
    }

    stoploss = -0.08

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ── 1h 지표 (4h 대비 더 빠른 신호) ──────────────
        dataframe['rsi']      = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx']      = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema']     = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200']   = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema8']     = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema21']    = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema50']    = ta.EMA(dataframe, timeperiod=50)
        dataframe['atr']      = ta.ATR(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe)
        dataframe['macd']     = macd['macd']
        dataframe['macd_sig'] = macd['macdsignal']

        # 추세 방향 판단 (EMA 배열)
        dataframe['trend_up']   = (dataframe['ema8'] > dataframe['ema21']).astype(int)
        dataframe['trend_down'] = (dataframe['ema8'] < dataframe['ema21']).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long: 1h 다중 필터
        dataframe.loc[
            (
                (dataframe['rsi'] > 52) &
                (dataframe['adx'] > 20) &
                (dataframe['tema'] > dataframe['ema200']) &
                (dataframe['macd'] > dataframe['macd_sig']) &
                (dataframe['trend_up'] == 1) &
                (dataframe['ema8'] > dataframe['ema50'])  # 중기 추세 확인
            ),
            'enter_long'] = 1

        # Short
        dataframe.loc[
            (
                (dataframe['rsi'] < 48) &
                (dataframe['adx'] > 20) &
                (dataframe['tema'] < dataframe['ema200']) &
                (dataframe['macd'] < dataframe['macd_sig']) &
                (dataframe['trend_down'] == 1) &
                (dataframe['ema8'] < dataframe['ema50'])
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1h EMA 역배열 시 즉시 청산 (4h보다 훨씬 빠름)
        dataframe.loc[
            (dataframe['ema8'] < dataframe['ema21']),
            'exit_long'] = 1
        dataframe.loc[
            (dataframe['ema8'] > dataframe['ema21']),
            'exit_short'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """수익 구간별 스탑로스 타이트화"""
        if current_profit > 0.05:
            return -0.01   # 본전 보호
        elif current_profit > 0.03:
            return -0.03   # 타이트 스탑
        return -0.08
