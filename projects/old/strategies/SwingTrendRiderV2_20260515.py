import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime, timedelta
from freqtrade.persistence import Trade

def hma(series, window):
    window = int(window)
    wma1 = ta.WMA(series, timeperiod=window // 2)
    wma2 = ta.WMA(series, timeperiod=window)
    return ta.WMA(2 * wma1 - wma2, timeperiod=int(np.sqrt(window)))

class SwingTrendRiderV2_20260515(IStrategy):
    INTERFACE_VERSION = 3

    # 전략 설정
    can_short: bool = True
    timeframe = '4h'
    
    # 수익률 1000%를 위한 공격적 설정 + 강력한 방어
    minimal_roi = {
        "0": 0.25,      # 25% 수익 시 즉시 실현
        "240": 0.15,    # 10봉(40시간) 후 15% 수익 시 실현
        "480": 0.08,    # 20봉 후 8% 수익 시 실현
        "720": 0.05     # 30봉 후 5% 수익 시 실현
    }

    # 손절 설정 (레버리지 5배 고려)
    stoploss = -0.08  # 최대 -8% (레버리지 적용 전) -> 실질적으로 -40% 손실 방지

    # 트레일링 스탑: 수익 보존의 핵심
    trailing_stop = True
    trailing_stop_positive = 0.015        # 1.5% 수익 확보 시 활성화
    trailing_stop_positive_offset = 0.03   # 3% 수익 도달 시 위 설정 활성화
    trailing_only_offset_is_reached = True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    # 파라미터 (최적화 반영)
    fastLen = 5
    slowLen = 20
    rsiLenR = 14
    adxLenR = 14
    atrLenR = 14
    
    bbLen = 20
    bbMult = 2.0
    
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 이평선
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=self.fastLen)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=self.slowLen)
        
        # RSI 및 ADX
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsiLenR)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adxLenR)
        
        # MACD (추세 강화 확인용)
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast, slowperiod=self.macd_slow, signalperiod=self.macd_signal)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # 거래량 필터 (가짜 돌파 방지)
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        
        # 볼린저 밴드
        bb = ta.BBANDS(dataframe, timeperiod=self.bbLen, nbdevup=self.bbMult, nbdevdn=self.bbMult)
        dataframe['bb_mid'] = bb['middleband']
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_lower'] = bb['lowerband']
        
        # ATR (동적 손절용)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atrLenR)
        
        # 레짐 판단 로직 강화
        dataframe['trend_up'] = (dataframe['fastEMA'] > dataframe['slowEMA']) & (dataframe['rsi'] > 52) & (dataframe['adx'] > 20)
        dataframe['trend_dn'] = (dataframe['fastEMA'] < dataframe['slowEMA']) & (dataframe['rsi'] < 48) & (dataframe['adx'] > 20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long Entry: 추세 + 모멘텀 + 거래량 + MACD
        dataframe.loc[
            (dataframe['trend_up']) &
            (dataframe['macdhist'] > 0) &
            (dataframe['macdhist'] > dataframe['macdhist'].shift(1)) &
            (dataframe['volume'] > dataframe['volume_mean'] * 0.8) &
            (dataframe['close'] < dataframe['bb_upper'] * 0.99), # 과열 진입 방지
            'enter_long'] = 1

        # Short Entry
        dataframe.loc[
            (dataframe['trend_dn']) &
            (dataframe['macdhist'] < 0) &
            (dataframe['macdhist'] < dataframe['macdhist'].shift(1)) &
            (dataframe['volume'] > dataframe['volume_mean'] * 0.8) &
            (dataframe['close'] > dataframe['bb_lower'] * 1.01),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 빠른 추세 반전 청산 (손실 최소화)
        dataframe.loc[
            (dataframe['fastEMA'] < dataframe['slowEMA']) |
            (dataframe['rsi'] < 45),
            'exit_long'] = 1

        dataframe.loc[
            (dataframe['fastEMA'] > dataframe['slowEMA']) |
            (dataframe['rsi'] > 55),
            'exit_short'] = 1

        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        # 초기 손절선: ATR 기반으로 더 타이트하게 (1.5 ATR)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        entry_candle = dataframe.loc[dataframe['date'] <= trade.open_date_utc].iloc[-1]
        
        atr_value = entry_candle['atr']
        if not trade.is_short:
            # 롱 포지션: 진입가 대비 1.5 ATR 손절
            sl_price = entry_candle['close'] - (atr_value * 1.5)
            return (sl_price / current_rate) - 1
        else:
            # 숏 포지션
            sl_price = entry_candle['close'] + (atr_value * 1.5)
            return 1 - (sl_price / current_rate)

    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str:
        
        # 수익 구간별 조기 청산 (수익 보존)
        if current_profit > 0.10: # 10% 수익 도달 시
            return "take_profit_10"
            
        # 손실이 -5%를 넘어가면(레버리지 전) 즉시 탈출 (Panic Exit)
        if current_profit < -0.05:
            return "panic_exit"
            
        return None

