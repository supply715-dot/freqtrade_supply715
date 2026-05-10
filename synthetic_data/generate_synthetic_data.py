import pandas as pd
import numpy as np

# --- 1. 설정 및 가상 데이터 시뮬레이션 파라미터 ---
START_DATE = '2023-06-01'
END_DATE = '2024-05-31' # 약 1년
TRADING_DAYS = pd.bdate_range(start=START_DATE, end=END_DATE)

# OHLCV (Daily Frequency - 기준 데이터)
def generate_ohlcv(dates):
    """OHLCV 데이터를 생성합니다. 트레이딩 데이에만 존재하도록 합니다."""
    np.random.seed(42)
    df = pd.DataFrame(index=dates)
    df['Open'] = np.random.uniform(100, 150, len(dates)).cumsum() * 0.99 + 100
    df['High'] = df['Open'] * (1 + np.random.rand(len(dates)) * 0.02)
    df['Low'] = df['Open'] * (1 - np.random.rand(len(dates)) * 0.02)
    df['Close'] = df['Open'] * (1 + np.random.randn(len(dates)) * 0.015)
    # Volume은 거래량으로 단순 생성
    df['Volume'] = np.random.randint(1000, 5000, len(dates))
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]

# Feature A: Market Sentiment Index (MSI) - Hourly Data를 Daily로 리샘플링하여 결측 유도
def generate_msi(start, end):
    """시간 간격이 다른 외부 데이터를 시뮬레이션합니다. 시간적 비정합성 테스트용."""
    dates = pd.date_range(start=start, end=end, freq='H') # Hourly data
    n = len(dates)
    msi = np.random.uniform(0.5, 1.5, n)
    df = pd.DataFrame({'MSI': msi}, index=pd.to_datetime(dates))
    return df

# Feature B: On-Chain Capital Flow (OCF) - 주간 데이터 시뮬레이션
def generate_ocf(start, end):
    """더 드문 주기(Weekly)의 데이터를 시뮬레이션하여 결측 유도."""
    dates = pd.date_range(start=start, end=end, freq='W-SUN') # Weekly data
    n = len(dates)
    ocf = np.random.normal(loc=10, scale=3, size=n)
    df = pd.DataFrame({'OCF': ocf}, index=pd.to_datetime(dates))
    return df

# --- 2. 데이터 정합성 및 보간 로직 구현 (Feature Orchestrator 핵심) ---

def feature_orchestration(ohlcv: pd.DataFrame, msi_hourly: pd.DataFrame, ocf_weekly: pd.DataFrame):
    """
    OHLCV를 기준으로 MSI와 OCF 데이터를 통합하고 결측치를 보간합니다.
    
    Args:
        ohlcv (pd.DataFrame): 일봉(Daily) OHLCV 데이터프레임. 
        msi_hourly (pd.DataFrame): 시간별(Hourly) MSI 데이터프레임.
        ocf_weekly (pd.DataFrame): 주간(Weekly) OCF 데이터프레임.
    Returns:
        pd.DataFrame: 모든 Feature가 표준화되고 통합된 최종 데이터셋.
    """
    print("--- [1/3] OHLCV 기준 Time Index 설정 및 정렬 ---")
    # 1단계: 가장 낮은 주기를 기준으로 시간 인덱스 생성 (OHLCV의 트레이딩 날짜)
    full_index = ohlcv.index

    # 2단계: MSI (Hourly -> Daily/Business Day) 처리
    print("--- [2/3] Feature A (MSI): Hourly -> Daily Aggregation & Interpolation ---")
    msi_daily = msi_hourly['MSI'].resample('D').mean().ffill() 
    # 주간 단위로 계산된 값을 일봉으로 변환하는 과정을 거쳤다고 가정하고, 누락치 발생 시 Forward Fill 적용

    # 3단계: OCF (Weekly -> Daily) 처리
    print("--- [3/3] Feature B (OCF): Weekly -> Daily Interpolation ---")
    ocf_daily = ocf_weekly['OCF'].resample('D').mean() # 주간 평균 계산
    ocf_daily = ocf_daily.ffill().bfill() # 누락된 일자(주말, 공휴일)는 앞뒤 값으로 채움

    # 4단계: 최종 통합 및 정제
    print("--- [4/3] Final DataFrame Merging ---")
    final_df = ohlcv.copy()
    
    # OHLCV 기준 인덱스를 사용하여 Feature를 병합 (결측치가 없는 날짜만 유지)
    for feature, series in zip(['MSI', 'OCF'], [msi_daily, ocf_daily]):
        final_df[feature] = series

    print("\n✅ 데이터 통합 및 정제 완료. 최종 DataFrame의 크기:", final_df.shape)
    return final_df.dropna() # 결측치가 너무 많은 행은 제거 (테스트 환경 가정)


# --- 3. 실행 블록 ---
if __name__ == "__main__":
    print("==================================================")
    print("✨ Researcher Data Standardization Pipeline Start")
    print("==================================================")

    # 1. 원본 데이터 생성 (가정)
    ohlcv_raw = generate_ohlcv(TRADING_DAYS)
    msi_hourly_raw = generate_msi(START_DATE, END_DATE)
    ocf_weekly_raw = generate_ocf(START_DATE, END_DATE)

    # 2. Orchestration 수행 및 데이터 정제 (핵심 로직 실행)
    standardized_df = feature_orchestration(ohlcv_raw, msi_hourly_raw, ocf_weekly_raw)

    # 3. 결과 저장
    output_path = 'synthetic_data/standardized_ohlcv_features_1y.csv'
    standardized_df.to_csv(output_path)
    print("\n==================================================")
    print(f"🎉 최종 데이터셋이 성공적으로 생성되어 저장되었습니다: {output_path}")
    print("개발자님께서는 이 파일을 백테스팅 엔진의 Input으로 사용해 주세요.")
    print("==================================================")