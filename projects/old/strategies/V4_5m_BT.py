import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
import talib.abstract as ta
from datetime import datetime
from freqtrade.persistence import Trade

class V4_5m_BT(IStrategy):
    """
    [백테스트용] 5m 패닉 감지 전략
    - 주 timeframe: 5m (최빠른 신호 감지)
    - RSI 과매도/과매수 + 거래량 폭증 감지
    - custom_stoploss로 계층적 손실 관리
    - 노이즈 필터링을 위해 ADX + EMA 200 필터 적용
    """
    INTERFACE_VERSION = 3

    can_short: bool = True
    timeframe = '5m'           # 5m을 메인으로 사용
    startup_candle_count: int = 200

    process_only_new_candles = True
    use_exit_signal = True

    minimal_roi = {
        "0": 0.40,
        "30": 0.20,     # 4h 기준 480분 → 5m 기준 30분
        "60": 0.10
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
        # ── 5m 지표 ──────────────────────────────────
        dataframe['rsi']      = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx']      = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema']     = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200']   = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema8']     = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema21']    = ta.EMA(dataframe, timeperiod=21)
        dataframe['atr']      = ta.ATR(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe)
        dataframe['macd']     = macd['macd']
        dataframe['macd_sig'] = macd['macdsignal']

        # 거래량 급증 감지 (20봉 평균의 3배 이상)
        dataframe['vol_ma']     = dataframe['volume'].rolling(20).mean()
        dataframe['vol_spike']  = (dataframe['volume'] > dataframe['vol_ma'] * 3.0).astype(int)

        # 패닉 급락: RSI < 20 + 거래량 폭증 + 음봉
        dataframe['panic_drop'] = (
            (dataframe['rsi'] < 20) &
            (dataframe['vol_spike'] == 1) &
            (dataframe['close'] < dataframe['open'])
        ).astype(int)

        # 패닉 급등: RSI > 80 + 거래량 폭증 + 양봉
        dataframe['panic_pump'] = (
            (dataframe['rsi'] > 80) &
            (dataframe['vol_spike'] == 1) &
            (dataframe['close'] > dataframe['open'])
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long: 5m 추세 상승 + 패닉 상황 아닐 때만 진입
        dataframe.loc[
            (
                (dataframe['rsi'] > 52) &
                (dataframe['adx'] > 20) &
                (dataframe['tema'] > dataframe['ema200']) &
                (dataframe['macd'] > dataframe['macd_sig']) &
                (dataframe['ema8'] > dataframe['ema21']) &
                (dataframe['panic_drop'] == 0)  # 패닉 상황 진입 금지
            ),
            'enter_long'] = 1

        # Short
        dataframe.loc[
            (
                (dataframe['rsi'] < 48) &
                (dataframe['adx'] > 20) &
                (dataframe['tema'] < dataframe['ema200']) &
                (dataframe['macd'] < dataframe['macd_sig']) &
                (dataframe['ema8'] < dataframe['ema21']) &
                (dataframe['panic_pump'] == 0)
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 5m EMA 역전 OR 패닉 급락 시 즉시 탈출
        dataframe.loc[
            (
                (dataframe['ema8'] < dataframe['ema21']) |
                (dataframe['panic_drop'] == 1)   # 패닉 즉시 탈출
            ),
            'exit_long'] = 1

        dataframe.loc[
            (
                (dataframe['ema8'] > dataframe['ema21']) |
                (dataframe['panic_pump'] == 1)
            ),
            'exit_short'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """계층적 스탑로스"""
        if current_profit > 0.05:
            return -0.01
        elif current_profit > 0.03:
            return -0.03
        return -0.08
