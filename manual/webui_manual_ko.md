# 📈 조나탄 AI 트레이딩: Freqtrade WebUI & API 서버 설치 및 사용법 가이드

본 설명서는 **SwingTrendRider V4_Active** 핵심 모델이 탑재된 조나탄 AI 트레이딩 시스템을 웹 브라우저(WebUI) 및 텔레그램을 통해 효율적으로 제어, 모니터링, 그리고 **설치 및 자동화(Setup)**하기 위한 종합 가이드라인입니다.

---

## 🛠️ 1. Freqtrade WebUI 및 API 서버 상세 Setup 가이드

Freqtrade WebUI를 구동하고 외부에서 모니터링하기 위해서는 백엔드 API 서버를 활성화하고 프론트엔드 패키지를 설치해야 합니다.

### ① WebUI 프론트엔드 패키지 설치
Freqtrade는 기본적으로 API 서버 기능만 내장되어 있으며, 시각적 인터페이스인 WebUI 파일은 최초 1회 별도 설치해 주어야 합니다. 터미널(PowerShell)에서 다음 명령어를 실행하십시오:

```powershell
# WebUI 정적 파일 자동 다운로드 및 설치
freqtrade install-ui
```
* **문제 해결**: 만약 인터넷 연결 문제나 권한 오류로 다운로드가 실패할 경우, Freqtrade가 구동 중인 가상환경(venv 등)이 활성화되어 있는지 확인해 주십시오.

### ② `config.json` API 서버 활성화 설정
WebUI의 포트, 로그인 계정 정보는 [config.json](file:///c:/Users/7supp/.gemini\antigravity/260509_freqtrade/config.json) 파일의 `api_server` 섹션에서 관리합니다.

```json
  "api_server": {
    "enabled": true,                  // API 서버 활성화 (필수: true)
    "listen_ip_address": "127.0.0.1", // 접속 대기 IP (로컬 PC 접속 시 기본값)
    "listen_port": 8080,              // 포트 번호 (기본값: 8080)
    "verbosity": "error",             // API 로그 상세도
    "enable_openapi": false,          // Swagger OpenAPI 활성화 여부
    "jwt_secret_key": "v-E_8Yv2R9T!zLp9W5K#jA2qG5N@mX8sP1uC4B7D0F3H6J9K", // JWT 토큰 서명 키
    "CORS_origins": [],               // 교차 출처 리소스 허용 주소
    "username": "freqtrader",         // WebUI 로그인 ID
    "password": "password"            // WebUI 로그인 비밀번호
  }
```

> [!IMPORTANT]
> **보안 권장사항 (Security Hardening)**
> 1. **비밀번호 변경**: 실거래 또는 공인 IP 환경 가동 시 `"password"` 값을 기본값에서 반드시 복잡한 문자열로 변경하십시오.
> 2. **JWT Secret Key 재발급**: 토큰 보안에 중요한 비밀키(`jwt_secret_key`) 역시 임의의 안전한 난수 문자열로 변경하여 외부 세션 하이재킹 공격을 미연에 방지하십시오.

### ③ 외부/원격 접속 설정 및 윈도우 방화벽 Open
사무실이나 외부 모바일 기기, 혹은 홈 네트워크 내 다른 PC에서 이 트레이딩 서버에 접속하고 싶다면 아래 설정을 순서대로 진행하십시오.

#### A. IP 바인딩 변경
[config.json](file:///c:/Users/7supp/.gemini\antigravity/260509_freqtrade/config.json) 내의 `listen_ip_address`를 로컬 주소에서 모든 네트워크 인터페이스 개방으로 수정합니다:
- 기존: `"listen_ip_address": "127.0.0.1"`
- **변경 후**: `"listen_ip_address": "0.0.0.0"`

#### B. 윈도우 방화벽 인바운드 포트 허용 (PowerShell 관리자 실행 필요)
윈도우 방화벽이 외부 접속 포트(`8080`)를 차단하고 있을 수 있습니다. 다음 명령어를 복사하여 **관리자 권한**으로 실행된 PowerShell에 입력하십시오:

```powershell
# 8080 포트에 대한 외부 접속 허용 인바운드 규칙 등록
New-NetFirewallRule -DisplayName "Freqtrade WebUI Allow" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

---

## ⚡ 2. 윈도우(Windows) 무중단 자동 구동 Setup

서버를 터미널 창을 켜둔 채로 놔두면 창이 실수로 닫혀 시스템이 정지될 위험이 있습니다. 백그라운드 자동 기동 및 무중단 가동을 위한 Setup 기법입니다.

### ① PowerShell 백그라운드 작업(Job) 구동법
터미널 창을 종료해도 백그라운드에서 트레이딩 봇이 안전하게 돌도록 프로세스를 격리 기동합니다:

```powershell
# 봇을 백그라운드 잡으로 무중단 구동 시작
Start-Job -Name "Jonathan_Trading_V4" -ScriptBlock {
    freqtrade trade --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --freqaimodel LightGBMRegressor --config config.json --dry-run
}
```

* **백그라운드 상태 모니터링**:
  ```powershell
  # 구동 중인 백그라운드 작업 조회
  Get-Job -Name "Jonathan_Trading_V4"
  
  # 실시간 백엔드 로그 확인
  Receive-Job -Name "Jonathan_Trading_V4" -Keep
  ```

### ② 윈도우 작업 스케줄러(Task Scheduler)를 이용한 부팅 시 자동 재기동
컴퓨터가 예기치 않게 재부팅되었을 때 자동으로 AI 봇을 구동하기 위한 배치 자동화 셋업입니다.

1. 워크스페이스 내에 `run_bot.bat` 배치 파일을 생성하고 아래 내용을 입력합니다:
   ```cmd
   @echo off
   cd /d "c:\Users\7supp\.gemini\antigravity\260509_freqtrade"
   freqtrade trade --strategy SwingTrendRiderV4_FreqAI_Active_20260515 --freqaimodel LightGBMRegressor --config config.json --dry-run
   ```
2. **윈도우 작업 스케줄러** 실행 ➔ **작업 만들기** 클릭.
3. **트리거** 탭: `컴퓨터 시작 시`로 설정.
4. **동작** 탭: `프로그램 시작` 선택 후 위에서 만든 `run_bot.bat` 파일 등록.
5. **조건 및 설정** 탭: `사용자가 로그온할 때만 실행` 해제, `가장 높은 수준의 권한으로 실행` 체크하여 설정 완료.

---

## 📱 3. 텔레그램(Telegram) 알림 봇 연동 및 Setup

원격 제어 및 진입/청산 실시간 브리핑을 텔레그램으로 수신하기 위한 셋업 절차입니다.

### ① 텔레그램 봇 생성 및 API Token 획득
1. 텔레그램 앱에서 **@BotFather**를 검색하여 대화를 시작합니다.
2. `/newbot` 명령어를 전송합니다.
3. 봇의 이름과 사용자 이름(Username, 반드시 `_bot`으로 끝나야 함)을 설정합니다.
4. 생성이 완료되면 `8688767961:AAFi85D14lw6...`와 같은 형태의 **HTTP API Token**이 발급됩니다. 이 토큰을 복사합니다.

### ② 사용자 Chat ID 알아내기
봇은 보안상 허용된 사용자에게만 명령을 받고 알림을 보내야 하므로 개인의 `chat_id`가 필요합니다.
1. 생성한 봇 대화방에 들어가서 `/start`를 보냅니다.
2. 텔레그램 검색창에 **@userinfobot**을 검색하여 대화를 시작합니다.
3. `/start`를 전송하면 화면에 즉시 본인의 고유 숫자 ID(예: `your_telegram_chat_id`)가 나타납니다. 이 값을 복사합니다.

### ③ `config.json`에 텔레그램 셋업 적용
[config.json](file:///c:/Users/7supp/.gemini\antigravity/260509_freqtrade/config.json)의 `telegram` 섹션을 열고 위에서 발급받은 정보들을 입력합니다:

```json
  "telegram": {
    "enabled": true,
    "token": "your_telegram_token", // 획득한 API Token 기입
    "chat_id": "your_telegram_chat_id"                                 // 본인의 Chat ID 기입
  }
```

---

## 🌐 4. WebUI 접속 및 로그인 방법

셋업이 완료되었다면 웹 브라우저를 통해 실시간으로 봇의 작동 상황과 AI 예측 차트를 시각적으로 모니터링할 수 있습니다.

* **접속 주소**: `http://127.0.0.1:8080` (또는 외부 IP)
* **로그인 정보**:
  * **ID (Username)**: `freqtrader`
  * **비밀번호 (Password)**: `password`

### 🚨 중요: "사이트에 연결할 수 없음" 오류 발생 시 대처법
WebUI는 Freqtrade 봇 프로세스(서버)가 활성화되어 **백그라운드 혹은 터미널에서 작동 중일 때만 접속이 가능**합니다.
봇이 꺼져 있거나 포트 `8080`이 방화벽 등으로 차단되어 있으면 접속 오류가 발생합니다.

* **해결책**: 터미널에서 봇이 정상 구동되어 최하단 로그에 `API Server started...` 메시지가 뜨는지 확인하시고, 외부 기기 접속 시에는 위에 기술된 **인바운드 방화벽 규칙** 등록 상태를 재점검해 주십시오.

---

## 📊 5. 핵심 화면 및 메뉴 가이드

WebUI 화면 왼쪽 또는 하단의 탐색 바를 통해 각 기능을 즉각 제어할 수 있습니다.

### ① 대시보드 (Dashboard)
봇의 전체적인 실시간 상태를 모니터링하는 메인 화면입니다.
- **현재 상태 (Status)**: 봇이 정상 구동 중인지(`Running`), 정지되었는지(`Stopped`) 확인합니다.
- **현재 수익률 (Today's Profit)**: 금일 청산 완료된 거래의 누적 수익금 및 수익률 실시간 시각 그래프.
- **열린 거래 (Open Trades)**: 보유 중인 포지션의 페어(BTC, ETH 등), 수량, 진입가, 실시간 미실현 손익(PnL) 실시간 파악.

### ② 진입 내역 (Trades)
현재 진입되어 보유하고 있는 각 포지션에 대한 수동 개입 제어판입니다.
- **Force Exit (강제 청산)** 버튼: AI 신호 전에 시장이 급변할 시, 클릭 한 번으로 거래소에 즉시 시장가 청산 주문을 보냅니다.

### ③ 거래 기록 (History)
과거에 성사 및 완료된 모든 거래 장부입니다.
- 진입/청산 시간, 체결 단가, 수량, 그리고 **청산 사유 (Exit Reason)**가 상세 보존됩니다.
  - `exit_signal`: 전략의 이평선 데드크로스 혹은 AI 판단으로 정밀 청산됨
  - `stop_loss`: 고정 하드 스탑로스(-8%)에 터치하여 안전 청산됨
  - `custom_stoploss`: 실시간 트레일링 스탑에 의해 본전 이상에서 익절 처리됨

### ④ 페어리스트 (Pairlist) 및 자산 현황 (Balance)
- **Pairlist**: 감시 화이트리스트(`BTC/USDT:USDT`, `ETH/USDT:USDT`)의 실시간 호가 및 변동률 관찰.
- **Balance**: 거래소와 연동된 총 자산 지갑 잔고, 증거금 비율, 거래 대기 예수금을 한눈에 시각 그래프로 확인.

---

## 🧠 6. FreqAI 머신러닝 모니터링법

대시보드 상에서 단순 캔들 차트가 아닌, **AI(LightGBM)의 예측 및 판단 데이터**를 추적하는 방법입니다.

### ① 💻 Logs (로그) 탭: "AI의 행동 상황판"
- AI가 캔들 정보를 바탕으로 기계학습 모델을 학습하는 일련의 과정(`Done training models...`) 및 피처 연산 상태 등의 **백엔드 AI 구동 연산 로그**를 관찰합니다.

### ② 📈 Charts (차트) 탭: "AI의 실시간 판단 시각화" ⭐
차트 설정 창의 **지표(Indicators) 선택 리스트**에서 다음 두 FreqAI 핵심 분석 지표를 활성화해 모니터링하십시오:
- **`&-target_roi`**: AI가 향후 6시간 동안의 기대 가격 변동률을 예측한 수치입니다. `0`선 위로 강하게 상승할 때 롱(Long), 아래로 꺾일 때 숏(Short) 신호의 핵심 기반이 됩니다.
- **`DI_ratio` (신뢰도 지표)**: AI가 현재 시장을 예측하기에 충분히 정상적이고 안전한 범주인지 판단하는 지표입니다.
  - `DI_ratio < 0.5`: AI가 시장 상황을 자신 있게 이해하고 있음 **(정상 매매 수행)**
  - `DI_ratio >= 0.5`: 변동성이 지나치게 높거나 머신러닝이 학습하지 못한 영역 **(안전을 위해 진입 자동 회피)**

---

## 💬 7. 텔레그램(Telegram) 원격 제어 실전 활용

연동이 완료된 텔레그램을 사용하여 야외에서도 간편하게 포지션을 제어하고 정보를 보고받을 수 있습니다.

### ⌨️ 필수 원격 명령어 리스트

| 명령어 | 기능 설명 |
| :--- | :--- |
| `/status` | 현재 진입해 있는 모든 포지션의 실시간 미실현 수익률 및 PnL 조회 |
| `/profit` | 시스템 기동 이후 누적된 전체 실현 손익 정밀 데이터 분석 리포트 수신 |
| `/balance` | 거래소(Binance 등) 지갑 내 보유 잔고 및 마진 사용 현황 확인 |
| `/daily` | 최근 7일간의 일별 상세 수익금 정밀 요약 정보 전송 |
| `/forceexit <trade_id>` | WebUI에 로그인하지 않고 특정 포지션을 시장가로 즉시 수동 강제 종료 |
| `/stop` | 봇의 신규 진입 감시 중단 (기존 진입 포지션에 대한 청산 관리는 계속 작동) |
| `/start` | 정지했던 봇의 신규 거래 진입 감시를 재개 |

---

## ⚠️ 모니터링 시 안전 규칙 및 주의사항

1. **레버리지 비율에 따른 리스크**: 현재 V4_Active는 5배 레버리지를 사용하므로, -8% 손절가 터치 시 원금 대비 약 **-40%** 수준의 자산 변동폭을 보입니다. 일시적인 차트 등락에 감정적으로 강제 청산 버튼을 누르기보다는 스탑로스 가드와 AI의 `DI_ratio` 회피 알고리즘을 신뢰하십시오.
2. **API 연결 끊김 알림**: WebUI 자산(Balance)이 한동안 업데이트되지 않거나 `Offline` 빨간색 오프라인 표시가 장시간 발생한다면, 거래소 API의 만료 여부나 서버의 네트워크 방화벽 차단 문제를 신속히 검사하십시오.

