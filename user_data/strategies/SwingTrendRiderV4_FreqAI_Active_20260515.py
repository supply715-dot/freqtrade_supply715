import logging
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
from datetime import datetime, timedelta, timezone
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)

class SwingTrendRiderV4_FreqAI_Active_20260515(IStrategy):
    INTERFACE_VERSION = 3

    # 전략 설정
    can_short: bool = True
    timeframe = '4h'
    startup_candle_count: int = 200
    
    # FreqAI 관련 설정
    process_only_new_candles = True
    use_exit_signal = True
    
    # ROI: AI가 관리하므로 더 유연하게 설정
    minimal_roi = {
        "0": 0.40,
        "480": 0.20,
        "960": 0.10
    }

    stoploss = -0.08 

    # 수수료 및 손절 연동형 시장가 최적화 설정 주입 (진입은 지정가 우선!)
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

    # 미체결 타임아웃 고속화 주입
    unfilledtimeout = {
        "entry": 2,
        "exit": 5,
        "unit": "minutes"
    }

    # 스마트 리밋 체이스 재시도 딕셔너리 및 런타임 제어 훅 (AWS Lambda 알고리즘 이식)
    _entry_retries = {}

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: str | None,
                            side: str, **kwargs) -> bool:
        # 만약 이 주문이 최종 시장가 폴백(Market Fallback) 주문이라면
        if order_type == 'market':
            logger.info(f"⚡ [Market Fallback] {pair} 시장가 진입 강제 집행 및 상태 리셋.")
            # 다음 진입을 위해 설정을 지정가('limit')로 즉시 원복
            self.order_types['entry'] = 'limit'
            self._entry_retries[pair] = 0
        else:
            # 첫 진입 또는 일반 지정가 시도 시 재시도 카운트 초기화
            if pair not in self._entry_retries:
                self._entry_retries[pair] = 0
            self.order_types['entry'] = 'limit'
            
        return True

    def check_entry_timeout(self, pair: str, trade: Trade, order: 'Order',
                            current_time: datetime, **kwargs) -> bool:
        # 스마트 리밋 체이스 감시 주기 (10초)
        retry_interval = 10 
        max_retries = 3

        # 주문 경과 시간 계산
        order_date = order.order_date.replace(tzinfo=timezone.utc) if order.order_date.tzinfo is None else order.order_date
        current_date = current_time.replace(tzinfo=timezone.utc) if current_time.tzinfo is None else current_time
        elapsed_seconds = (current_date - order_date).total_seconds()

        # 만약 주문이 지정된 간격(10초)보다 더 오랫동안 체결되지 않고 방치되었다면
        if elapsed_seconds > retry_interval:
            retries = self._entry_retries.get(pair, 0)
            
            # 지정가 N회 시도 미만인 경우: 취소 후 다른 호가로 재시도
            if retries < (max_retries - 1):
                self._entry_retries[pair] = retries + 1
                logger.info(f"🔁 [Limit Chase {retries + 1}/{max_retries}] {pair} 지정가 미체결 취소 및 다음 틱 호가 갱신 시도. (경과: {elapsed_seconds:.1f}초)")
                return True # True를 리턴하면 Freqtrade가 주문을 즉각 취소하고, 다음 틱에서 새로운 지정가를 보냅니다.
            
            # 최종 N회 시도마저 실패한 경우: 취소 후 다음 주문을 시장가(Market)로 발주하도록 런타임 강제 전환!
            else:
                self._entry_retries[pair] = max_retries
                self.order_types['entry'] = 'market'
                logger.warning(f"🚨 [Limit Chase 최종 실패] {pair} 지정가 {max_retries}회 시도 실패. 즉시 시장가(Market) 진입으로 런타임 전환! (경과: {elapsed_seconds:.1f}초)")
                return True # True를 리턴하여 현재 지정가를 취소하고, 다음 루프에서 시장가 주문이 나가도록 함.

        return False

    # 트레일링 스탑
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    # -------------------------------------------------------------------------
    # FreqAI: 피처 엔지니어링 (학습 데이터 생성)
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
    # 지표 및 신호
    # -------------------------------------------------------------------------
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # FreqAI 예측 수행
        dataframe = self.freqai.start(dataframe, metadata, self)
        
        # 기본 지표
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['fastEMA'] = ta.EMA(dataframe, timeperiod=8)
        dataframe['slowEMA'] = ta.EMA(dataframe, timeperiod=24)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 공격적 세팅 (Active Mode) ---
        prediction_threshold = 0.012 # 2.0% -> 1.2% 로 하향
        adx_min = 20                 # 25 -> 20 으로 하향
        rsi_long = 52                # 55 -> 52 로 하향
        rsi_short = 48               # 45 -> 48 로 상향 (범위 확대)
        di_limit = 0.5               # 데이터 신뢰도 필터 (약간 완화)
        
        if 'DI_ratio' not in dataframe.columns:
            dataframe['DI_ratio'] = 0.0
        if 'do_predict' not in dataframe.columns:
            dataframe['do_predict'] = 0

        # Long Entry: AI 예측 + 추세 필터
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] > prediction_threshold) &
                (dataframe['rsi'] > rsi_long) &
                (dataframe['adx'] > adx_min) &
                (dataframe['tema'] > dataframe['ema200'])
            ),
            'enter_long'] = 1

        # Short Entry
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] < -prediction_threshold) &
                (dataframe['rsi'] < rsi_short) &
                (dataframe['adx'] > adx_min) &
                (dataframe['tema'] < dataframe['ema200'])
            ),
            'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 추세가 완전히 꺾이면 탈출
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
