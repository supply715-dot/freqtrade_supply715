import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair
import talib.abstract as ta
from datetime import datetime
from freqtrade.persistence import Trade

class SwingTrendRiderV5_1h4h_20260516(IStrategy):
    """
    ✅ SwingTrendRider V5 (2026-05-16)
    ─────────────────────────────────
    구조: 1h 메인 + 4h informative 진입 필터
    ─────────────────────────────────
    - 메인 타임프레임: 1h
      → 1h EMA 크로스 기반 청산 (빠른 반응)
      → 급락 감지 후 빠른 탈출 가능
    - 4h informative: 진입 방향 필터
      → 4h EMA200 위/아래 → 롱/숏 방향 제한
      → 4h 추세와 반대 방향 진입 금지
    - FreqAI 예측: 1h 봉 기준 학습/예측
    - 5배 레버리지 (선물 거래)
    - 계층적 custom_stoploss (수익 구간별 타이트화)
    """
    INTERFACE_VERSION = 3

    # ── 핵심 설정 ──────────────────────────────────
    can_short: bool = True
    timeframe = '1h'                  # 메인: 1h (빠른 청산 반응)
    startup_candle_count: int = 200

    process_only_new_candles = True
    use_exit_signal = True

    # ── ROI (1h 기준 재조정) ────────────────────────
    minimal_roi = {
        "0":   0.40,
        "120": 0.20,   # 120분 = 2시간 후
        "240": 0.10    # 240분 = 4시간 후
    }

    stoploss = -0.08

    # ── 트레일링 스탑 ───────────────────────────────
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    # ──────────────────────────────────────────────
    # 레버리지 (5x 고정)
    # ──────────────────────────────────────────────
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str,
                 side: str, **kwargs) -> float:
        return 5.0

    # ──────────────────────────────────────────────
    # informative pairs 선언 (4h 데이터 수집)
    # ──────────────────────────────────────────────
    def informative_pairs(self):
        """4h 데이터를 추가로 수집 (1h 메인 전략의 추세 필터용)"""
        pairs = self.dp.current_whitelist()
        return [(pair, '4h') for pair in pairs]

    # ──────────────────────────────────────────────
    # FreqAI: 피처 엔지니어링 (1h 봉 기반 학습)
    # ──────────────────────────────────────────────
    def feature_engineering_expand_all(self, dataframe: DataFrame, period: int,
                                       metadata: dict, **kwargs) -> DataFrame:
        dataframe[f"%-ema_{period}"]        = ta.EMA(dataframe, timeperiod=period)
        dataframe[f"%-rsi_{period}"]        = ta.RSI(dataframe, timeperiod=period)
        macd = ta.MACD(dataframe)
        dataframe[f"%-macd_{period}"]       = macd['macd']
        dataframe[f"%-macdhist_{period}"]   = macd['macdhist']
        dataframe[f"%-atr_{period}"]        = ta.ATR(dataframe, timeperiod=period)
        dataframe[f"%-pct_change_{period}"] = dataframe['close'].pct_change(period)
        return dataframe

    def feature_engineering_expand_basic(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
        return dataframe

    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        # 1h 기준: 6봉 후 수익 예측 (= 약 6시간 후)
        dataframe["&-target_roi"] = (
            dataframe["close"].shift(-6) / dataframe["close"] - 1
        )
        return dataframe

    # ──────────────────────────────────────────────
    # 지표 계산 (1h 기본 + 4h informative 병합)
    # ──────────────────────────────────────────────
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # ── 1. FreqAI 예측 (1h 봉 기반) ─────────────
        dataframe = self.freqai.start(dataframe, metadata, self)

        # ── 2. 1h 기본 지표 ─────────────────────────
        dataframe['rsi']     = ta.RSI(dataframe, timeperiod=14)
        dataframe['adx']     = ta.ADX(dataframe, timeperiod=14)
        dataframe['tema']    = ta.TEMA(dataframe, timeperiod=9)
        dataframe['ema200']  = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema8']    = ta.EMA(dataframe, timeperiod=8)
        dataframe['ema21']   = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema50']   = ta.EMA(dataframe, timeperiod=50)
        dataframe['atr']     = ta.ATR(dataframe, timeperiod=14)

        # ── 3. 4h informative 지표 (추세 방향 필터) ──
        inf_4h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='4h')

        inf_4h['ema200_4h']     = ta.EMA(inf_4h, timeperiod=200)
        inf_4h['ema50_4h']      = ta.EMA(inf_4h, timeperiod=50)
        inf_4h['rsi_4h']        = ta.RSI(inf_4h, timeperiod=14)
        inf_4h['adx_4h']        = ta.ADX(inf_4h, timeperiod=14)

        # 4h 추세 방향 (EMA200 기준)
        inf_4h['bull_trend_4h'] = (inf_4h['close'] > inf_4h['ema200_4h']).astype(int)
        inf_4h['bear_trend_4h'] = (inf_4h['close'] < inf_4h['ema200_4h']).astype(int)

        # 4h 강한 추세 (ADX 기준)
        inf_4h['strong_trend_4h'] = (inf_4h['adx_4h'] > 25).astype(int)

        # 1h 데이터프레임에 4h 데이터 병합
        # (1h 메인 + 4h informative → 정상 방향, Freqtrade 표준 지원)
        dataframe = merge_informative_pair(dataframe, inf_4h, '1h', '4h', ffill=True)

        return dataframe

    # ──────────────────────────────────────────────
    # 진입 신호 (1h 지표 + 4h 추세 필터 복합)
    # ──────────────────────────────────────────────
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # FreqAI 컬럼 존재 여부 안전 처리
        if 'DI_ratio' not in dataframe.columns:
            dataframe['DI_ratio'] = 0.0
        if 'do_predict' not in dataframe.columns:
            dataframe['do_predict'] = 0

        prediction_threshold = 0.012   # AI 예측 최소 수익 임계값
        adx_min = 20
        rsi_long = 50
        rsi_short = 50
        di_limit = 0.5

        # ── Long Entry ──────────────────────────────
        # 조건: 1h AI 예측 상승 + 1h 지표 상승 + 4h 상승 추세 확인
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] > prediction_threshold) &
                (dataframe['rsi'] > rsi_long) &
                (dataframe['adx'] > adx_min) &
                (dataframe['ema8'] > dataframe['ema21']) &       # 1h 단기 상승
                (dataframe['tema'] > dataframe['ema200']) &      # 1h 장기 상승
                (dataframe['bull_trend_4h_4h'] == 1)            # ✅ 4h 상승 추세 필터
            ),
            'enter_long'] = 1

        # ── Short Entry ─────────────────────────────
        # 조건: 1h AI 예측 하락 + 1h 지표 하락 + 4h 하락 추세 확인
        dataframe.loc[
            (
                (dataframe['do_predict'] == 1) &
                (dataframe['DI_ratio'] < di_limit) &
                (dataframe['&-target_roi'] < -prediction_threshold) &
                (dataframe['rsi'] < rsi_short) &
                (dataframe['adx'] > adx_min) &
                (dataframe['ema8'] < dataframe['ema21']) &       # 1h 단기 하락
                (dataframe['tema'] < dataframe['ema200']) &      # 1h 장기 하락
                (dataframe['bear_trend_4h_4h'] == 1)            # ✅ 4h 하락 추세 필터
            ),
            'enter_short'] = 1

        return dataframe

    # ──────────────────────────────────────────────
    # 청산 신호 (1h 봉 기준 → 4h보다 빠른 반응)
    # ──────────────────────────────────────────────
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        # 1h EMA 크로스 역전 시 즉시 청산 (4h보다 최대 3봉 빨리 반응)
        dataframe.loc[
            (dataframe['ema8'] < dataframe['ema21']),
            'exit_long'] = 1

        dataframe.loc[
            (dataframe['ema8'] > dataframe['ema21']),
            'exit_short'] = 1

        return dataframe

    # ──────────────────────────────────────────────
    # custom_stoploss: 수익 구간별 계층적 손실 관리
    # ──────────────────────────────────────────────
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        수익 구간별 스탑로스 타이트화:
        - 수익 +5% 이상: -1% (본전 보호, 이익 확보)
        - 수익 +3% 이상: -3% (타이트 스탑)
        - 그 외       : -8% (기본 안전망)
        """
        if current_profit > 0.05:
            return -0.01    # 본전 + α 보호
        elif current_profit > 0.03:
            return -0.03    # 중간 타이트
        return -0.08        # 기본 스탑
