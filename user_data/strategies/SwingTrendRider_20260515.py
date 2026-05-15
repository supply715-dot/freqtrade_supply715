import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime, timedelta
from freqtrade.persistence import Trade

# Hull Moving Average implementation
def hma(series, window):
    window = int(window)
    wma1 = ta.WMA(series, timeperiod=window // 2)
    wma2 = ta.WMA(series, timeperiod=window)
    return ta.WMA(2 * wma1 - wma2, timeperiod=int(np.sqrt(window)))

class SwingTrendRider_20260515(IStrategy):
    """
    4H Swing · Regime + Momentum [V1.2] Trend Rider
    Converted from Pine Script V1.2
    """
    INTERFACE_VERSION = 3

    # Strategy parameters
    can_short: bool = True
    timeframe = '4h'

    # ROI table: No ROI for this strategy, managed by custom_exit
    minimal_roi = {
        "0": 10.0  # High value to disable standard ROI
    }

    # Stoploss: Managed by custom_stoploss
    stoploss = -0.99  # Loose stoploss, real one in custom_stoploss

    # Trailing stop: Disabled as per V1.2 philosophy
    trailing_stop = False

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    # Parameters
    fastLen = 5
    slowLen = 20
    rsiLenR = 5
    adxLenR = 7
    atrLenR = 14
    rsiHi = 60.0
    rsiLo = 40.0
    adxHi = 25.0
    distSt = 1.0
    minReg = 2

    momLen = 20
    momSmooth = 5
    zLen = 100
    momFiltLen = 7

    bbLen = 20
    bbMult = 2.0
    bbBuffer = 1.05

    closeSLAtr = 3.0
    emergSLAtr = 5.0
    
    rsiExitLen = 14
    rsiExitHi = 78
    rsiExitLo = 22
    
    timeStopBars = 10
    timeStopMinPct = 0.5

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=self.fastLen)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=self.slowLen)
        
        # RSI
        dataframe['rsi_regime'] = ta.RSI(dataframe, timeperiod=self.rsiLenR)
        dataframe['rsi_exit'] = ta.RSI(dataframe, timeperiod=self.rsiExitLen)
        
        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adxLenR)
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atrLenR)
        
        # Distance (%)
        dataframe['dist'] = (dataframe['fastEMA'] - dataframe['slowEMA']).abs() / dataframe['slowEMA'] * 100.0
        
        # --- Regime Calculation ---
        def calc_regime(row):
            isUp = (row['fastEMA'] > row['slowEMA']) and (row['rsi_regime'] > 55) and (row['adx'] > 15)
            isDn = (row['fastEMA'] < row['slowEMA']) and (row['rsi_regime'] < 45) and (row['adx'] > 15)
            
            reg = 0
            if isUp:
                s = 1
                if row['rsi_regime'] >= self.rsiHi: s += 1
                if row['adx'] >= self.adxHi or row['dist'] >= self.distSt: s += 1
                reg = min(3, s)
            elif isDn:
                s = 1
                if row['rsi_regime'] <= self.rsiLo: s += 1
                if row['adx'] >= self.adxHi or row['dist'] >= self.distSt: s += 1
                reg = -min(3, s)
            else:
                reg = 1 if row['fastEMA'] > row['slowEMA'] else -1 if row['fastEMA'] < row['slowEMA'] else 0
            return reg

        dataframe['regimeRaw'] = dataframe.apply(calc_regime, axis=1)
        
        # --- Momentum Calculation ---
        emaM = ta.EMA(dataframe, timeperiod=self.momLen)
        dataframe['mom_raw'] = 100.0 * (emaM - emaM.shift(self.momLen)) / emaM.shift(self.momLen).replace(0, np.nan)
        dataframe['mom_sm'] = ta.EMA(dataframe['mom_raw'], timeperiod=self.momSmooth)
        
        # Z-Score
        dataframe['mom_mn'] = dataframe['mom_sm'].rolling(window=self.zLen).mean()
        dataframe['mom_sd'] = dataframe['mom_sm'].rolling(window=self.zLen).std()
        dataframe['mom_score'] = (dataframe['mom_sm'] - dataframe['mom_mn']) / dataframe['mom_sd'].replace(0, np.nan)
        dataframe['mom_score'] = dataframe['mom_score'].clip(-3.0, 3.0)
        
        # HMA Filter
        dataframe['mom_filt'] = hma(dataframe['mom_score'], self.momFiltLen)
        dataframe['mom_dir'] = 0
        dataframe.loc[dataframe['mom_filt'] > dataframe['mom_filt'].shift(1), 'mom_dir'] = 1
        dataframe.loc[dataframe['mom_filt'] < dataframe['mom_filt'].shift(1), 'mom_dir'] = -1
        
        # Final Regime
        dataframe['regimeFinal'] = (dataframe['regimeRaw'] + (dataframe['mom_score'] * 0.5).round()).clip(-3, 3)
        
        # Bollinger Bands
        bb = ta.BBANDS(dataframe, timeperiod=self.bbLen, nbdevup=self.bbMult, nbdevdn=self.bbMult)
        dataframe['bb_mid'] = bb['middleband']
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_lower'] = bb['lowerband']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long Entry
        dataframe.loc[
            (dataframe['regimeFinal'] >= self.minReg) &
            (dataframe['mom_dir'] == 1) &
            (dataframe['close'] < dataframe['bb_mid'] * self.bbBuffer),
            'enter_long'] = 1

        # Long Jump Entry (V-shape)
        dataframe.loc[
            (dataframe['regimeFinal'] >= 2) &
            (dataframe['regimeFinal'].shift(1) <= -1) &
            (dataframe['enter_long'] != 1),
            ['enter_long', 'enter_tag']] = [1, 'long_jump']

        # Short Entry
        dataframe.loc[
            (dataframe['regimeFinal'] <= -self.minReg) &
            (dataframe['mom_dir'] == -1) &
            (dataframe['close'] > dataframe['bb_mid'] * (2.0 - self.bbBuffer)),
            'enter_short'] = 1

        # Short Jump Entry
        dataframe.loc[
            (dataframe['regimeFinal'] <= -2) &
            (dataframe['regimeFinal'].shift(1) >= 1) &
            (dataframe['enter_short'] != 1),
            ['enter_short', 'enter_tag']] = [1, 'short_jump']

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit Signal Logic (2/3 conditions)
        
        # Long Exit
        dataframe['exit_sig_l'] = 0
        dataframe.loc[dataframe['regimeFinal'] <= 0, 'exit_sig_l'] += 1
        dataframe.loc[dataframe['mom_dir'] == -1, 'exit_sig_l'] += 1
        dataframe.loc[dataframe['close'] < dataframe['slowEMA'], 'exit_sig_l'] += 1
        
        dataframe.loc[dataframe['exit_sig_l'] >= 2, 'exit_long'] = 1

        # Short Exit
        dataframe['exit_sig_s'] = 0
        dataframe.loc[dataframe['regimeFinal'] >= 0, 'exit_sig_s'] += 1
        dataframe.loc[dataframe['mom_dir'] == 1, 'exit_sig_s'] += 1
        dataframe.loc[dataframe['close'] > dataframe['slowEMA'], 'exit_sig_s'] += 1
        
        dataframe.loc[dataframe['exit_sig_s'] >= 2, 'exit_short'] = 1

        return dataframe

    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        # Partial Profit (RSI) - In backtesting, we simulate this as a full exit or ignore
        # Note: Freqtrade doesn't support 50% exit easily in a single custom_exit call without adjust_trade_position
        # For simplicity in this backtest, we'll mark it as a reason but exit fully if it's over the extreme.
        if trade.is_short:
            if last_candle['rsi_exit'] <= self.rsiExitLo:
                return "rsi_partial_exit_short"
        else:
            if last_candle['rsi_exit'] >= self.rsiExitHi:
                return "rsi_partial_exit_long"

        # Time Stop
        trade_duration = (current_time - trade.open_date_utc).total_seconds() // (60 * 60 * 4) # in 4h bars
        if trade_duration >= self.timeStopBars and current_profit < (self.timeStopMinPct / 100):
            return "time_stop"

        # Hard Stop Loss (Close based 3.0 ATR)
        # This is handled here because it's "close based"
        if not trade.is_short:
            # Long Close SL
            entry_candle = dataframe.loc[dataframe['date'] <= trade.open_date_utc].iloc[-1]
            stop_price = entry_candle['close'] - (self.closeSLAtr * entry_candle['atr'])
            if current_rate < stop_price:
                return "close_stoploss_long"
        else:
            # Short Close SL
            entry_candle = dataframe.loc[dataframe['date'] <= trade.open_date_utc].iloc[-1]
            stop_price = entry_candle['close'] + (self.closeSLAtr * entry_candle['atr'])
            if current_rate > stop_price:
                return "close_stoploss_short"

        return None

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        # Emergency Hard Stop (5.0 ATR - Tick based)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        entry_candle = dataframe.loc[dataframe['date'] <= trade.open_date_utc].iloc[-1]
        
        atr_value = entry_candle['atr']
        if not trade.is_short:
            stop_price = entry_candle['close'] - (self.emergSLAtr * atr_value)
            # Convert price to relative stoploss
            return (stop_price / current_rate) - 1
        else:
            stop_price = entry_candle['close'] + (self.emergSLAtr * atr_value)
            return 1 - (stop_price / current_rate)

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str, 
                            side: str, **kwargs) -> bool:
        # Check if it's a jump entry to reduce position size
        # This is handled via custom logic if needed, but for backtest we'll just log it.
        return True

