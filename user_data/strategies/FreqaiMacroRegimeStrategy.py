import logging
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np
from pandas import DataFrame
import talib.abstract as ta

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, stoploss_from_open

logger = logging.getLogger(__name__)


class FreqaiMacroRegimeStrategy(IStrategy):
    """
    Pine Script (Macro Regime Engine V18.4) -> FreqAI 변환 v2
    
    [v2 개선사항]
    - AI 진입 임계값 상향: 0.008 → 0.015 (확신 높을 때만 진입)
    - trailing_stop 비활성화 → custom_stoploss 단독 작동 명확화
    - Long/Short 양방향 진입 활성화 (can_short=True)
    - AI 진입 확신도 필터 강화 (롱은 +1.5%, 숏은 -1.5%)
    - custom_stoploss가 기본 stoploss보다 우선 작동하도록 정리
    """

    # ─── 기본 설정 ─────────────────────────────────────────
    timeframe = "5m"
    startup_candle_count: int = 200

    # [v12] 목표 달성을 위한 기계적 손익비(1:1) 스캘핑 
    # 승률이 50% 이상만 나오면 무조건 누적 수익이 발생하는 구조
    minimal_roi = {
        "0": 0.01   # 1% 고정 익절
    }

    # 고정 손절 (1:1 비율)
    stoploss = -0.01
    trailing_stop = False
    use_custom_stoploss = False  # 버그를 유발하던 커스텀 손절 제거
    
    can_short = False

    # ─── 타임프레임 설정 ───────────────────────────────────

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '1h') for pair in pairs]

    # ─── FreqAI Feature Engineering ─────────────────────────

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        dataframe[f'%-tema_{period}'] = ta.TEMA(dataframe, timeperiod=period)
        bb = ta.BBANDS(dataframe, timeperiod=period)
        dataframe[f'%-bb_width_{period}'] = (bb['upperband'] - bb['lowerband']) / bb['middleband'].replace(0, np.nan)
        dataframe[f'%-rsi_{period}'] = ta.RSI(dataframe, timeperiod=period)
        
        macd = ta.MACD(dataframe)
        dataframe[f'%-macdhist_{period}'] = macd['macdhist']
        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        dataframe['rsi_val'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['%-ema_50'] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        # 15봉(75분) 뒤의 파동 타겟 (1% 익절 목표이므로 짧게)
        target = (
            (dataframe["close"].shift(-15) - dataframe["close"])
            / dataframe["close"]
        )
        dataframe["&-future_roi_15"] = target.ffill()
        return dataframe

    # ─── 지표 계산 (FreqAI 트리거) ──────────────────────────

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema_50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['rsi_14'] = ta.RSI(dataframe, timeperiod=14)
        macd = ta.MACD(dataframe)
        dataframe['macd_hist'] = macd['macdhist']
        
        # FreqAI 시작
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe

    # ─── 진입 / 청산 조건 (기계적 매매) ───────────────────────

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        [v12] 빈도수 극대화 및 기계적 진입
        """
        enter_long = (
            (df["do_predict"] == 1) &
            (df["&-future_roi_15"] > 0.003) &  # 타겟 임계값을 0.3%로 낮춰 빈도 폭발적 증가
            (df['close'] > df['ema_50']) &     # 최소한의 추세 동행
            (df['macd_hist'] > 0)
        )
        df.loc[enter_long, ["enter_long", "enter_tag"]] = (1, "rr_long_v12")
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """청산은 전적으로 ROI 1%와 Stoploss -1%에 맡깁니다."""
        return df

    # ─── 커스텀 손절 로직 (v9 노이즈 방어형) ──────────────────

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        [v9] ATR 기반 동적 손절 - 배수 확장 (4 -> 6)
        노이즈에 의한 조기 손절을 방지하여 승률을 높입니다.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return -0.10

        last_candle = dataframe.iloc[-1].squeeze()

        if "stable_atr" in last_candle:
            # 6배 ATR 손절 (노이즈 방어)
            atr_stop = (6.0 * last_candle['stable_atr']) / current_rate
            return max(-0.15, -atr_stop) # 최대 -15% 제한

        return -0.10
