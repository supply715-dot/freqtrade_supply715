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
    INTERFACE_VERSION = 3
    timeframe = "5m"
    startup_candle_count: int = 200
    can_short = True 
    minimal_roi = {"0": 100}
    # Solution 3: Tighter Stoploss
    stoploss = -0.10 
    trailing_stop = True
    trailing_stop_positive_offset = 0.02
    trailing_stop_positive = 0.005
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
        # Base: Martingale
        return proposed_stake * 0.10

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '1h') for pair in pairs]

    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        dataframe[f'%-rsi_{period}'] = ta.RSI(dataframe, timeperiod=period)
        dataframe[f'%-tema_{period}'] = ta.TEMA(dataframe, timeperiod=period)
        dataframe[f'%-adx_{period}'] = ta.ADX(dataframe, timeperiod=period)
        dataframe[f'%-roc_{period}'] = ta.ROC(dataframe, timeperiod=period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        dataframe['%-ema_20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['%-ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['%-ema_100'] = ta.EMA(dataframe, timeperiod=100)
        return dataframe

    def feature_engineering_standard(self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs) -> DataFrame:
        target = ((dataframe["close"].shift(-10) - dataframe["close"]) / dataframe["close"])
        dataframe["&-future_roi_10"] = target.ffill()
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema_100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        enter_long = ((df["do_predict"] == 1) & (df["&-future_roi_10"] > 0.003) & (df['rsi_14'] < 40) & (df['ema_50'] > df['ema_100']))
        df.loc[enter_long, ["enter_long", "enter_tag"]] = (1, "dca_long")
        enter_short = ((df["do_predict"] == 1) & (df["&-future_roi_10"] < -0.003) & (df['rsi_14'] > 60) & (df['ema_50'] < df['ema_100']))
        df.loc[enter_short, ["enter_short", "enter_tag"]] = (1, "dca_short")
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        return df

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float, min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float, current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        if current_profit > -0.01:
            return None
        filled_entries = trade.select_filled_orders(trade.entry_side)
        count_of_entries = len(filled_entries)
        # Base: Martingale
        if count_of_entries == 1 and current_profit <= -0.020:
            return trade.stake_amount 
        if count_of_entries == 2 and current_profit <= -0.045:
            return trade.stake_amount 
        if count_of_entries == 3 and current_profit <= -0.080:
            return trade.stake_amount 
        return None
