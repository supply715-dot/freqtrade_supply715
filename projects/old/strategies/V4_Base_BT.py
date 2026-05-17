import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair
import talib.abstract as ta
from datetime import datetime
from freqtrade.persistence import Trade

class V4_Base_BT(IStrategy):
    """
    [백테스트용] 기준선 전략 - informative timeframe 없음
    FreqAI 제거, 순수 지표 기반으로 백테스트 비교
    """
    INTERFACE_VERSION = 3

    can_short: bool = True
    timeframe = '4h'
    startup_candle_count: int = 200

    process_only_new_candles = True
    use_exit_signal = True

    minimal_roi = {
        "0": 0.40,
        "480": 0.20,
        "960": 0.10
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
        dataframe['rsi']      = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx']      = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema']     = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200']   = ta.EMA(dataframe, timeperiod=200)
        dataframe['fastEMA']  = ta.EMA(dataframe, timeperiod=8)
        dataframe['slowEMA']  = ta.EMA(dataframe, timeperiod=24)
        dataframe['atr']      = ta.ATR(dataframe, timeperiod=14)

        # 볼린저 밴드
        bb = ta.BBANDS(dataframe, timeperiod=20)
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_mid']   = bb['middleband']

        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd']     = macd['macd']
        dataframe['macd_sig'] = macd['macdsignal']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long Entry
        dataframe.loc[
            (
                (dataframe['rsi'] > 52) &
                (dataframe['adx'] > 20) &
                (dataframe['tema'] > dataframe['ema200']) &
                (dataframe['macd'] > dataframe['macd_sig']) &
                (dataframe['fastEMA'] > dataframe['slowEMA'])
            ),
            'enter_long'] = 1

        # Short Entry
        dataframe.loc[
            (
                (dataframe['rsi'] < 48) &
                (dataframe['adx'] > 20) &
                (dataframe['tema'] < dataframe['ema200']) &
                (dataframe['macd'] < dataframe['macd_sig']) &
                (dataframe['fastEMA'] < dataframe['slowEMA'])
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['fastEMA'] < dataframe['slowEMA']),
            'exit_long'] = 1
        dataframe.loc[
            (dataframe['fastEMA'] > dataframe['slowEMA']),
            'exit_short'] = 1
        return dataframe
