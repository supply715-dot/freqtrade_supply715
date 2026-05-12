import logging
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np
from pandas import DataFrame
import talib.abstract as ta

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)

class FreqaiMacroRegimeStrategy(IStrategy):
    """
    [v21] 1h FreqAI DCA Swing Bot
    1시간봉 스윙 + 5배 레버리지 + -10% 하드손절 + 마팅게일 DCA
    """
    INTERFACE_VERSION = 3
    timeframe = "1h" # 5분봉에서 1시간봉으로 상향 (노이즈 제거)
    startup_candle_count: int = 200

    can_short = True 
    minimal_roi = {"0": 100}
    
    # [핵심] 가장 성과가 좋았던 -10% 타이트한 하드 손절 유지
    stoploss = -0.10 

    # 트레일링 스탑: 1시간봉 스윙이므로 익절 목표를 상향 (3% 상승 시 활성화)
    trailing_stop = True
    trailing_stop_positive_offset = 0.030  # 3.0% 상승 시 활성화 (5배 레버리지 = 15% 수익)
    trailing_stop_positive = 0.005         # 고점 대비 0.5% 하락 시 익절
    trailing_only_offset_is_reached = True

    use_custom_stoploss = False
    
    position_adjustment_enable = True
    max_entry_position_adjustment = 3

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 5.0

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str], side: str,
                            **kwargs) -> float:
        # 배수 물타기를 위해 초기 진입은 시드의 10%로 제한
        return proposed_stake * 0.10

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '4h') for pair in pairs]

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        dataframe[f'%-rsi_{period}'] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f'%-tema_{period}'] = ta.TEMA(dataframe, timeperiod=period)
        dataframe[f'%-adx_{period}'] = ta.ADX(dataframe, timeperiod=period)
        dataframe[f'%-roc_{period}'] = ta.ROC(dataframe, timeperiod=period)
        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        dataframe['%-ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['%-ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['%-ema_100'] = ta.EMA(dataframe, timeperiod=100)
        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        return dataframe

    def set_freqai_targets(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        # 1시간봉에서 10캔들 = 10시간 뒤의 가격 예측 (진정한 스윙)
        target = (
            (dataframe["close"].shift(-10) - dataframe["close"])
            / dataframe["close"]
        )
        dataframe["&-future_roi_10"] = target.ffill()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        # Long: 1시간봉 기준 1% 이상 큰 상승이 예측될 때 진입
        enter_long = (
            (df["do_predict"] == 1) &
            (df["&-future_roi_10"] > 0.01) & 
            (df['rsi_14'] < 50) &             
            (df['ema_50'] > df['ema_100'])
        )
        df.loc[enter_long, ["enter_long", "enter_tag"]] = (1, "swing_long")

        # Short: 1시간봉 기준 1% 이상 큰 하락이 예측될 때 진입
        enter_short = (
            (df["do_predict"] == 1) &
            (df["&-future_roi_10"] < -0.01) & 
            (df['rsi_14'] > 50) &             
            (df['ema_50'] < df['ema_100'])
        )
        df.loc[enter_short, ["enter_short", "enter_tag"]] = (1, "swing_short")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        return df

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        
        if current_profit > -0.01:
            return None

        filled_entries = trade.select_filled_orders(trade.entry_side)
        count_of_entries = len(filled_entries)

        # 1시간봉에 맞는 널널한 그리드 간격 (2%, 4%, 6%) 적용
        # 1차 물타기: 가격이 -2.0% 하락 시
        if count_of_entries == 1 and current_profit <= -0.020:
            return trade.stake_amount 

        # 2차 물타기: 가격이 -4.0% 하락 시
        if count_of_entries == 2 and current_profit <= -0.040:
            return trade.stake_amount 

        # 3차 물타기: 가격이 -6.0% 하락 시 (-10% 손절까지 4%의 여유 방어막)
        if count_of_entries == 3 and current_profit <= -0.060:
            return trade.stake_amount 

        return None
