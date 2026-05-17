import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair
import talib.abstract as ta
from datetime import datetime
from freqtrade.persistence import Trade

class V5_1h4h_BT(IStrategy):
    """
    [백테스트 검증용] V5 순수 지표 버전
    - 메인: 1h, informative: 4h 추세 필터
    - FreqAI 제거 (백테스트 비교용)
    """
    INTERFACE_VERSION = 3

    can_short: bool = True
    timeframe = '1h'
    startup_candle_count: int = 200

    process_only_new_candles = True
    use_exit_signal = True

    minimal_roi = {
        "0":   0.40,
        "120": 0.20,
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

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '4h') for pair in pairs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ── 1h 기본 지표 ──────────────────────────────
        dataframe['rsi']    = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx']    = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema']   = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema8']   = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema21']  = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema50']  = ta.EMA(dataframe, timeperiod=50)
        dataframe['atr']    = ta.ATR(dataframe, timeperiod=14)

        macd = ta.MACD(dataframe)
        dataframe['macd']     = macd['macd']
        dataframe['macd_sig'] = macd['macdsignal']

        # ── 4h informative (1h 메인에 병합 → Freqtrade 정상 지원) ─
        inf_4h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='4h')

        inf_4h['ema200_4h']      = ta.EMA(inf_4h, timeperiod=200)
        inf_4h['ema50_4h']       = ta.EMA(inf_4h, timeperiod=50)
        inf_4h['rsi_4h']         = ta.RSI(inf_4h, timeperiod=14)
        inf_4h['adx_4h']         = ta.ADX(inf_4h, timeperiod=14)

        inf_4h['bull_trend_4h']  = (inf_4h['close'] > inf_4h['ema200_4h']).astype(int)
        inf_4h['bear_trend_4h']  = (inf_4h['close'] < inf_4h['ema200_4h']).astype(int)
        inf_4h['strong_trend_4h']= (inf_4h['adx_4h'] > 25).astype(int)

        # ✅ 1h(메인) ← 4h(느린봉 informative): Freqtrade 정상 지원
        dataframe = merge_informative_pair(dataframe, inf_4h, '1h', '4h', ffill=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long: 1h 지표 상승 + 4h 상승 추세 확인
        dataframe.loc[
            (
                (dataframe['rsi'] > 52) &
                (dataframe['adx'] > 20) &
                (dataframe['ema8'] > dataframe['ema21']) &
                (dataframe['tema'] > dataframe['ema200']) &
                (dataframe['macd'] > dataframe['macd_sig']) &
                (dataframe['bull_trend_4h_4h'] == 1)     # 4h 상승 추세 필터
            ),
            'enter_long'] = 1

        # Short: 1h 지표 하락 + 4h 하락 추세 확인
        dataframe.loc[
            (
                (dataframe['rsi'] < 48) &
                (dataframe['adx'] > 20) &
                (dataframe['ema8'] < dataframe['ema21']) &
                (dataframe['tema'] < dataframe['ema200']) &
                (dataframe['macd'] < dataframe['macd_sig']) &
                (dataframe['bear_trend_4h_4h'] == 1)     # 4h 하락 추세 필터
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1h EMA 크로스 시 즉시 청산
        dataframe.loc[(dataframe['ema8'] < dataframe['ema21']), 'exit_long'] = 1
        dataframe.loc[(dataframe['ema8'] > dataframe['ema21']), 'exit_short'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        if current_profit > 0.05:
            return -0.01
        elif current_profit > 0.03:
            return -0.03
        return -0.08
