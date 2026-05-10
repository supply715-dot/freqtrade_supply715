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

    # Pine Script 대응 ROI 테이블 (0분:4%, 30분:2%, 60분:1%)
    minimal_roi = {
        "0":  0.04,
        "30": 0.02,
        "60": 0.01,
    }

    # [핵심 수정 1] trailing_stop 완전 비활성화
    # → trailing_stop_loss 로 인한 전패 114건 방지
    # → custom_stoploss()가 단독으로 ATR 기반 동적 손절을 담당
    trailing_stop = False

    # [핵심 수정 2] 기본 stoploss를 넉넉하게 (-20%)
    # → custom_stoploss가 먼저 4 ATR 기준으로 손절하므로
    #    이 값은 custom_stoploss가 이상 동작할 때의 최후 보험
    stoploss = -0.20

    use_exit_signal = True
    use_custom_stoploss = True   # custom_stoploss() 함수 활성화
    process_only_new_candles = True

    # [핵심 수정 3] 양방향 거래 활성화
    can_short = True

    # ─── FreqAI Feature Engineering ─────────────────────────

    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        """
        period 파라미터를 지표 기간으로 직접 사용.
        config_freqai.json의 indicator_periods_candles: [5, 14, 20]
        """
        # EMA 이격도 (추세 방향 및 강도)
        ema_fast = ta.EMA(dataframe, timeperiod=max(2, period // 2))
        ema_slow = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-ema_dist_pct_{period}"] = (
            (ema_fast - ema_slow) / ema_slow.replace(0, np.nan) * 100
        )

        # RSI (과매수/과매도)
        dataframe[f"%-rsi_{period}"] = ta.RSI(dataframe, timeperiod=period)

        # ADX (추세 강도)
        dataframe[f"%-adx_{period}"] = ta.ADX(dataframe, timeperiod=period)

        # ATR 대비 캔들 크기 비율 (변동성 충격 감지)
        atr = ta.ATR(dataframe, timeperiod=period)
        candle_range = dataframe["high"] - dataframe["low"]
        dataframe[f"%-candle_vs_atr_{period}"] = candle_range / atr.replace(0, np.nan)

        # BBW (볼린저 밴드 폭, 횡보 vs 추세 구분)
        bb = ta.BBANDS(dataframe, timeperiod=period, nbdevup=2.0, nbdevdn=2.0)
        dataframe[f"%-bbw_{period}"] = (
            (bb["upperband"] - bb["lowerband"])
            / bb["middleband"].replace(0, np.nan)
            * 100
        )

        # SMA 기울기 (추세의 방향성)
        sma = ta.SMA(dataframe, timeperiod=period)
        dataframe[f"%-sma_slope_{period}"] = sma - sma.shift(1)

        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        """모든 period에 공통으로 계산되는 기본 지표."""
        # CVD 모방: 양봉이면 +volume, 음봉이면 -volume으로 누적 흐름 파악
        vol_dir = np.where(dataframe["close"] >= dataframe["open"], 1, -1)
        dataframe["%-pseudo_cvd_10"] = (
            (dataframe["volume"] * vol_dir).rolling(window=10).sum()
        )

        # 거래량 비율 (현재 거래량 / 20봉 평균)
        dataframe["%-vol_ratio"] = (
            dataframe["volume"] / dataframe["volume"].rolling(20).mean().replace(0, np.nan)
        )

        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        """시간 기반 Feature."""
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        return dataframe

    def set_freqai_targets(
        self, dataframe: DataFrame, metadata: Dict[str, Any], **kwargs
    ) -> DataFrame:
        """
        [AI 정답지 (Target)] AI에게 '15봉 뒤 수익률을 맞춰봐'라고 지시합니다.
        마지막 15봉 NaN → ffill()로 채움 (학습 데이터 공백 방지)
        """
        target = (
            (dataframe["close"].shift(-15) - dataframe["close"])
            / dataframe["close"]
        )
        dataframe["&-future_roi_15"] = target.ffill()
        return dataframe

    # ─── 지표 계산 (FreqAI 트리거) ──────────────────────────

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """FreqAI 학습/예측 파이프라인 실행 및 ATR 계산."""
        dataframe = self.freqai.start(dataframe, metadata, self)
        # custom_stoploss에서 ATR 기반 동적 손절 계산에 사용
        # 3봉 전 ATR: 급격한 변동성 캔들의 오염 방지
        dataframe["stable_atr"] = ta.ATR(dataframe, timeperiod=14).shift(3)
        return dataframe

    # ─── 진입 / 청산 조건 ────────────────────────────────────

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """
        [핵심 수정 4] AI 임계값 상향 (0.008 → 0.015)
        확신이 매우 높을 때만 진입 → 잡음 진입 대폭 감소
        롱/숏 양방향 지원
        """
        # 롱 진입: AI가 +1.5% 이상 상승 예측
        enter_long = (
            (df["do_predict"] == 1)
            & (df["&-future_roi_15"] > 0.015)
        )
        df.loc[enter_long, ["enter_long", "enter_tag"]] = (1, "freqai_long")

        # 숏 진입: AI가 -1.5% 이상 하락 예측
        enter_short = (
            (df["do_predict"] == 1)
            & (df["&-future_roi_15"] < -0.015)
        )
        df.loc[enter_short, ["enter_short", "enter_tag"]] = (1, "freqai_short")

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        """AI 예측이 반대 방향으로 바뀌면 즉시 탈출."""
        # 롱 포지션 청산: AI가 하락(-0.3% 이하) 예측으로 전환
        exit_long = (
            (df["do_predict"] == 1)
            & (df["&-future_roi_15"] < -0.003)
        )
        df.loc[exit_long, ["exit_long", "exit_tag"]] = (1, "freqai_exit")

        # 숏 포지션 청산: AI가 상승(+0.3% 이상) 예측으로 전환
        exit_short = (
            (df["do_predict"] == 1)
            & (df["&-future_roi_15"] > 0.003)
        )
        df.loc[exit_short, ["exit_short", "exit_tag"]] = (1, "freqai_exit")

        return df

    # ─── 리스크 관리 ─────────────────────────────────────────

    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> float:
        """
        [동적 손절 v2] trailing_stop 완전 제거 후 이 함수 단독으로 손절 관리.

        단계별 손절 전략:
          Phase 1 (0~60분): 4.0 ATR — 노이즈 파동 완전 무시
          Phase 2 (60~120분): 3.0 ATR — 슬슬 조여오기
          Phase 3 (120분 이상, 수익 1% 미만): 2.5 ATR — 결단
          Phase 4 (수익 3% 이상): 본절 + 1.0 ATR — 수익 보호
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return -0.20

        last_candle = dataframe.iloc[-1].squeeze()
        atr = last_candle.get("stable_atr", 0)

        if not atr or pd.isna(atr) or atr == 0:
            return -0.20

        atr_pct = atr / trade.open_rate
        minutes_in_trade = (current_time - trade.open_date_utc).total_seconds() / 60

        # Phase 4: 수익 3% 이상 → 수익 보호 모드 (본절 + 1 ATR)
        if current_profit >= 0.03:
            sl_pct = -(atr_pct * 1.0)
            # stoploss_from_open은 오픈가 기준 손절이 본절(0%) 아래로 내려가지 않게 보호
            return stoploss_from_open(
                max(sl_pct, -current_profit + atr_pct),
                current_profit,
                is_short=trade.is_short
            )

        # Phase 1: 첫 60분 → 넉넉한 4.0 ATR (휩소 방지)
        if minutes_in_trade <= 60:
            sl_pct = -(atr_pct * 4.0)

        # Phase 2: 60~120분 → 3.0 ATR
        elif minutes_in_trade <= 120:
            sl_pct = -(atr_pct * 3.0)

        # Phase 3: 120분 이상 + 수익 1% 미만 → 2.5 ATR 조임
        else:
            sl_pct = -(atr_pct * 2.5)

        return stoploss_from_open(sl_pct, current_profit, is_short=trade.is_short)

    def custom_exit(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """
        [스마트 청산 v2] AI 뷰가 급격히 악화되면 손절선 도달 전에 먼저 탈출.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        ai_predict = last_candle.get("&-future_roi_15", 0)

        if trade.is_short:
            # 숏: AI가 상승으로 뷰 전환 + 약손실 이내 → 탈출
            if current_profit > -0.008 and ai_predict > 0.008:
                return "ai_view_reversed_exit"
        else:
            # 롱: AI가 하락으로 뷰 전환 + 약손실 이내 → 탈출
            if current_profit > -0.008 and ai_predict < -0.008:
                return "ai_view_reversed_exit"

        return None
