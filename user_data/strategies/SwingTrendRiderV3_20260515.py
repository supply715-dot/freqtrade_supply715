import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime, timedelta
from freqtrade.persistence import Trade

class SwingTrendRiderV3_20260515(IStrategy):
    INTERFACE_VERSION = 3

    # 전략 설정
    can_short: bool = True
    timeframe = '4h'
    
    # ROI: 스윙 트레이더의 호흡으로 조정 (수익률 1000% 목표)
    minimal_roi = {
        "0": 0.40,      # 40% 수익 시 실현
        "480": 0.20,    # 20봉(80시간) 후 20% 수익 시 실현
        "960": 0.10,    # 40봉 후 10% 수익 시 실현
        "1440": 0.05    # 60봉 후 5% 수익 시 실현
    }

    # 손절 설정
    stoploss = -0.10  # 10% (레버리지 5배 시 -50%)

    # 트레일링 스탑: 조금 더 여유 있게
    trailing_stop = True
    trailing_stop_positive = 0.025        # 2.5% 수익 확보 시 활성화
    trailing_stop_positive_offset = 0.06   # 6% 수익 도달 시 위 설정 활성화
    trailing_only_offset_is_reached = True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    # 파라미터 (스윙 최적화)
    fastLen = 8
    slowLen = 24
    rsiLen = 14
    adxLen = 14
    atrLen = 14
    
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 이평선 (조금 더 느리게)
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=self.fastLen)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=self.slowLen)
        
        # RSI 및 기울기
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsiLen)
        dataframe['rsi_slope'] = dataframe['rsi'].diff(3) # 3봉 전 대비 RSI 변화
        
        # ADX (강한 추세 확인)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adxLen)
        
        # MACD
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast, slowperiod=self.macd_slow, signalperiod=self.macd_signal)
        dataframe['macdhist'] = macd['macdhist']
        
        # 거래량 및 ATR
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atrLen)
        
        # 추세 조건
        dataframe['strong_trend_up'] = (dataframe['fastEMA'] > dataframe['slowEMA']) & (dataframe['adx'] > 25)
        dataframe['strong_trend_dn'] = (dataframe['fastEMA'] < dataframe['slowEMA']) & (dataframe['adx'] > 25)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long Entry: 강한 추세 + RSI 상승세 + MACD 양수
        dataframe.loc[
            (dataframe['strong_trend_up']) &
            (dataframe['rsi_slope'] > 0) &
            (dataframe['rsi'] > 50) &
            (dataframe['macdhist'] > 0) &
            (dataframe['volume'] > dataframe['volume_mean'] * 0.9),
            'enter_long'] = 1

        # Short Entry
        dataframe.loc[
            (dataframe['strong_trend_dn']) &
            (dataframe['rsi_slope'] < 0) &
            (dataframe['rsi'] < 50) &
            (dataframe['macdhist'] < 0) &
            (dataframe['volume'] > dataframe['volume_mean'] * 0.9),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 추세가 확연히 꺾일 때만 청산
        dataframe.loc[
            (dataframe['fastEMA'] < dataframe['slowEMA'] * 0.99) |
            (dataframe['rsi'] < 40),
            'exit_long'] = 1

        dataframe.loc[
            (dataframe['fastEMA'] > dataframe['slowEMA'] * 1.01) |
            (dataframe['rsi'] > 60),
            'exit_short'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        # 손절선: 2.0 ATR로 조금 더 여유를 줌 (휩소 방지)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        entry_candle = dataframe.loc[dataframe['date'] <= trade.open_date_utc].iloc[-1]
        
        atr_value = entry_candle['atr']
        if not trade.is_short:
            sl_price = entry_candle['close'] - (atr_value * 2.0)
            return (sl_price / current_rate) - 1
        else:
            sl_price = entry_candle['close'] + (atr_value * 2.0)
            return 1 - (sl_price / current_rate)

    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str:
        
        # 패닉 엑시트: -7% 도달 시 즉시 탈출
        if current_profit < -0.07:
            return "panic_exit"
            
        return None

