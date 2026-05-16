def run_simulation():
    initial_capital = 10000  # $10,000 시작
    leverage = 5

    # 1. 7만 -> 12만 롱 (Long) 포지션
    p_entry1 = 70000
    p_exit1 = 120000
    price_change1 = (p_exit1 - p_entry1) / p_entry1  # 50000 / 70000 = 71.43%
    roi1 = price_change1 * leverage                 # 71.43% * 5 = 357.14%
    capital_after_long = initial_capital * (1 + roi1)

    # 2. 12만 -> 6만 숏 (Short) 포지션
    p_entry2 = 120000
    p_exit2 = 60000
    price_change2 = (p_exit2 - p_entry2) / p_entry2  # -60000 / 120000 = -50.00%
    roi2 = (-price_change2) * leverage               # 50.00% * 5 = 250.00%
    final_capital = capital_after_long * (1 + roi2)

    total_roi = (final_capital - initial_capital) / initial_capital
    multiple = final_capital / initial_capital

    print("=" * 50)
    print(" [ 비트코인 스윙 레버리지 x5 시뮬레이션 결과 ]")
    print("=" * 50)
    print(f"초기 자본: ${initial_capital:,.2f}")
    print(f"\n[1단계: 7만 -> 12만 Long x5]")
    print(f" - 자산 가격 변동: +{price_change1*100:.2f}%")
    print(f" - 레버리지 수익률: +{roi1*100:.2f}%")
    print(f" - 1단계 후 자본: ${capital_after_long:,.2f}")

    print(f"\n[2단계: 12만 -> 6만 Short x5]")
    print(f" - 자산 가격 변동: {price_change2*100:.2f}%")
    print(f" - 레버리지 수익률: +{roi2*100:.2f}%")
    print(f" - 최종 자본: ${final_capital:,.2f}")

    print("=" * 50)
    print(f"최종 누적 수익률: +{total_roi*100:.2f}%")
    print(f"최종 자산 배수: 원금의 {multiple:.2f}배")
    print("=" * 50)

if __name__ == "__main__":
    run_simulation()
