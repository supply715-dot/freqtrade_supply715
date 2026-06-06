import logging
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
from datetime import datetime, timedelta, timezone
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)

GLOBAL_DATAFRAMES = {}

# ?섏뼱蹂?理쒖쥌 理쒖쟻???뚮씪誘명꽣 留?
import json
import os

PAIR_PARAMS_DEFAULT = {
    'BTC/USDT:USDT': {
        'adx_long': 20,
        'adx_short': 28,
        'rsi_long': 43,
        'rsi_short': 40,
        'prediction_threshold': 0.012,
        'prediction_short_threshold': 0.005,
        'leverage_long': 8,
        'leverage_short': 3,
        'ema_filter': 'ema100'
    },
    'ETH/USDT:USDT': {
        'adx_long': 20,
        'adx_short': 22,
        'rsi_long': 42,
        'rsi_short': 45,
        'prediction_threshold': 0.008,
        'prediction_short_threshold': 0.006,
        'leverage_long': 9,
        'leverage_short': 7,
        'ema_filter': 'ema150'
    }
}

PAIR_PARAMS_PATH = os.path.join(os.path.dirname(__file__), 'V10_BTC_ETH_pair_params.json')
if os.path.exists(PAIR_PARAMS_PATH):
    try:
        with open(PAIR_PARAMS_PATH, 'r') as f:
            PAIR_PARAMS = json.load(f)
    except Exception as e:
        logger.error(f"Error loading custom pair params: {e}")
        PAIR_PARAMS = PAIR_PARAMS_DEFAULT
else:
    PAIR_PARAMS = PAIR_PARAMS_DEFAULT

class V10_BTC_ETH_optimized(IStrategy):
    INTERFACE_VERSION = 3

    # ?꾨왂 ?ㅼ젙
    can_short: bool = True
    timeframe = '4h'
    startup_candle_count: int = 200
    
    # FreqAI 愿???ㅼ젙
    process_only_new_candles = False
    use_exit_signal = True

    # ?섏씠?쇱샃?몄슜 怨듯넻 ?뺤쓽 (諛깊뀒?ㅽ듃 ???숈쟻 遺꾧린 濡쒖쭅???덉쑝誘濡??뷀뤃???뚮젅?댁뒪?????븷)
    prediction_threshold = DecimalParameter(0.005, 0.050, default=0.010, space='buy', decimals=3, optimize=False)

    # ROI: AI媛 愿由ы븯誘濡??좎뿰?섍쾶 ?곸슜
    minimal_roi = {
        "0": 0.40,
        "480": 0.20,
        "960": 0.10
    }

    stoploss = -0.08 

    # ?섏닔猷?諛??먯젅 ?곕룞???쒖옣媛 理쒖쟻???ㅼ젙 二쇱엯
    order_types = {
        "entry": "limit",
        "exit": "market",
        "emergency_exit": "market",
        "force_entry": "market",
        "force_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": True,
        "stoploss_price_type": "last",
        "stoploss_on_exchange_limit_ratio": 0.99
    }

    # 誘몄껜寃???꾩븘??怨좎냽??二쇱엯
    unfilledtimeout = {
        "entry": 2,
        "exit": 5,
        "unit": "minutes"
    }

    _entry_retries = {}

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str | None,
                            side: str, **kwargs) -> bool:
        if order_type == 'market':
            logger.info(f"??[Market Fallback] {pair} ?쒖옣媛 吏꾩엯 媛뺤젣 吏묓뻾 諛??곹깭 由ъ뀑.")
            self.order_types['entry'] = 'limit'
            self._entry_retries[pair] = 0
        else:
            if pair not in self._entry_retries:
                self._entry_retries[pair] = 0
            self.order_types['entry'] = 'limit'
            
        return True

    def check_entry_timeout(self, pair: str, trade: Trade, order: 'Order',
                            current_time: datetime, **kwargs) -> bool:
        retry_interval = 10 
        max_retries = 3

        order_date = order.order_date.replace(tzinfo=timezone.utc) if order.order_date.tzinfo is None else order.order_date
        current_date = current_time.replace(tzinfo=timezone.utc) if current_time.tzinfo is None else current_time
        elapsed_seconds = (current_date - order_date).total_seconds()

        if elapsed_seconds > retry_interval:
            retries = self._entry_retries.get(pair, 0)
            
            if retries < (max_retries - 1):
                self._entry_retries[pair] = retries + 1
                logger.info(f"?봺 [Limit Chase {retries + 1}/{max_retries}] {pair} 吏?뺢? 誘몄껜寃?痍⑥냼 諛??ㅼ쓬 ???멸? 媛깆떊 ?쒕룄. (寃쎄낵: {elapsed_seconds:.1f}珥?")
                return True 
            
            else:
                self._entry_retries[pair] = max_retries
                self.order_types['entry'] = 'market'
                logger.warning(f"?슚 [Limit Chase 理쒖쥌 ?ㅽ뙣] {pair} 吏?뺢? {max_retries}???쒕룄 ?ㅽ뙣. 利됱떆 ?쒖옣媛(Market) 吏꾩엯?쇰줈 ?고????꾪솚! (寃쎄낵: {elapsed_seconds:.1f}珥?")
                return True 

        return False

    # ?몃젅?쇰쭅 ?ㅽ깙
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        params = PAIR_PARAMS.get(pair, PAIR_PARAMS['BTC/USDT:USDT'])
        base_leverage = float(params['leverage_short']) if side == 'short' else float(params['leverage_long'])
        
        # v3 媛쒖꽑: ?κ린 ?섎씫??close < ema200)??踰좎뼱留덉폆 援?㈃?먯꽌留??덈쾭由ъ?瑜??꾨쭔?섍쾶 ??땄
        if side == 'long':
            dataframe = GLOBAL_DATAFRAMES.get(pair)
            if dataframe is not None and not dataframe.empty:
                try:
                    idx = self._get_df_idx(dataframe, current_time)
                    close = dataframe.loc[idx].get('close', current_rate)
                    ema200 = dataframe.loc[idx].get('ema200', current_rate)
                    if close < ema200:
                        de_rated = 6.0 if pair == 'ETH/USDT:USDT' else 5.0
                        logger.info(f"?썳截?[Leverage De-rating] {pair} close < ema200. Leverage {base_leverage} -> {de_rated}")
                        return de_rated
                except Exception as e:
                    logger.error(f"Error in dynamic leverage scaling v3: {e}")
                
        return base_leverage

    # -------------------------------------------------------------------------
    # FreqAI: ?쇱쿂 ?붿??덉뼱留?(?숈뒿 ?곗씠???앹꽦)
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
    # 吏??諛??좏샇
    # -------------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI ?덉륫 ?섑뻾
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 湲곕낯 吏??
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=100)
        dataframe['ema150'] = ta.EMA(dataframe, timeperiod=150)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=24)
        
        # MACD 吏곸젒 怨꾩궛
        macd = ta.MACD(dataframe)
        dataframe['macdhist'] = macd['macdhist']
        
        GLOBAL_DATAFRAMES[metadata['pair']] = dataframe.copy()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']
        params = PAIR_PARAMS.get(pair, PAIR_PARAMS['BTC/USDT:USDT'])
        
        di_limit = 0.5               
        if 'DI_ratio' not in dataframe.columns:
            dataframe['DI_ratio'] = 0.0
        if 'do_predict' not in dataframe.columns:
            dataframe['do_predict'] = 0

        # v3 媛쒖꽑: 踰좎뼱留덉폆 濡?吏꾩엯 ?λ꼍 ?꾪솕 ?쒗봽??(0.016 -> 0.010濡?議곗젙?섏뿬 媛吏?諛섎벑? 留됰릺 ?ㅼ젣 諛붾떏 諛섎벑? ?ъ갑)
        long_threshold = pd.Series(params['prediction_threshold'], index=dataframe.index)
        if pair == 'ETH/USDT:USDT':
            long_threshold.loc[dataframe['close'] < dataframe['ema200']] = 0.010

        # Long Entry
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] > long_threshold) &
                (dataframe['rsi'] > params['rsi_long']) &
                (dataframe['adx'] > params['adx_long']) &
                (dataframe['tema'] > dataframe['ema200'])
            ),
            'enter_long'] = 1

        # Short Entry
        ema_col = params['ema_filter']
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] < -params['prediction_short_threshold']) &
                (dataframe['rsi'] < params['rsi_short']) &
                (dataframe['adx'] > params['adx_short']) &
                (dataframe['fastEMA'] < dataframe['slowEMA']) &
                (dataframe['close'] < dataframe[ema_col]) &
                (dataframe['macdhist'] < 0)
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

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        return -0.08

    def _get_df_idx(self, dataframe, target_time) -> int:
        df_dates = pd.to_datetime(dataframe['date']).dt.tz_localize(None)
        target_naive = target_time.replace(tzinfo=None)
        past_candles = df_dates[df_dates <= target_naive - timedelta(hours=4)]
        if not past_candles.empty:
            return past_candles.index[-1]
        return dataframe.index[-1]

    def custom_exit(self, pair: str, trade: 'Trade', current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str | bool | None:
        dataframe = GLOBAL_DATAFRAMES.get(pair)
        if dataframe is None or dataframe.empty:
            if self.dp:
                dataframe = self.dp.get_pair_dataframe(pair, self.timeframe)
            if dataframe is None or dataframe.empty:
                return None
        try:
            # v3 媛쒖꽑: ???꾩슜 trailing profit exit 濡쒖쭅 ??젣 (?ㅻ━吏??trailing_stop??100% ?꾩엫?섏뿬 ?⑹룜 議곌린 ?몃┝ 李⑤떒)
            idx = self._get_df_idx(dataframe, trade.open_date)
            di_ratio = dataframe.loc[idx].get('DI_ratio', 0.0)
            
            # ?대뜑由ъ?/鍮꾪듃肄붿씤 怨좊??숈꽦 濡???鍮꾨?移?삎 dynamic stoploss ?ㅺ퀎
            if trade.is_short:
                dynamic_sl = -0.06 + (di_ratio * 0.06)
                dynamic_sl = max(-0.06, min(-0.03, dynamic_sl))
            else:
                dynamic_sl = -0.08 + (di_ratio * 0.08)
                dynamic_sl = max(-0.08, min(-0.04, dynamic_sl))
            
            if current_profit <= dynamic_sl:
                return "di_continuous_stoploss"
        except Exception as e:
            logger.error(f"Error in custom_exit for V6_Hybrid_Optimized_Combined: {e}")
        return None
