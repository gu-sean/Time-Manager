# 시간 관리 매니저 (Time Manager)

Windows용 데스크탑 시간 추적 앱입니다.  
포어그라운드 앱과 브라우저 URL을 자동으로 감지하여 활동 시간을 **생산적 / 비생산적 / 중립** 으로 분류하고, 하루의 시간 흐름을 분석합니다.

---

## 기능

### 자동 활동 추적
- 몇 초마다 현재 포어그라운드 앱을 기록
- `uiautomation`으로 Chromium 계열 브라우저 URL 추출
- 키보드·마우스 입력 없이 5분이 지나면 자동 추적 일시정지

### 분류 규칙
- `rules.json` 기반 도메인·앱·창 제목 키워드 규칙
- 기본값은 **중립 우선** — 새 앱·사이트는 분류 전까지 중립으로 취급
- Rules 탭에서 JSON 편집 없이 추가·수정·삭제 가능

### 활동 정리함
- 기록된 활동 검색·삭제·복원
- 앱·URL·창 제목 키워드 검색 (최근 30일)

### 데일리 리뷰
- 선택 날짜의 생산적 활동·최대 방해 요소·미분류 항목 요약
- 세션·전환 횟수 기반 흐름 분석
- 25분 이상 집중 블록 감지

### 리포트
- 최근 7일 / 30일 / 이번 달 생산성 통계
- 24시간 활동 차트 및 일별 생산성 점수 추세선
- 취약 시간대·반복 방해 요소·요일 패턴 분석
- CSV 내보내기 (오늘 / 기간별 / 날짜 범위)

### 개인화 및 설정
- 역할별 스타터 프리셋 (개발자·학생·사무직·크리에이터 등)
- 일일/주간 생산 목표, 비생산 시간 상한, 근무 시간 설정
- 데이터 보존 기간, 자동 백업 (최근 4개 유지), 수동 백업·복원
- 다크 모드 / 라이트 모드
- Windows 시작 시 자동 실행

### 맞춤 분류 추천 · 코칭
- **내장 분석 (기본, 무료)** — 전송 없이 PC에서만 처리
  - 분류 추천: 분류 기록·내 규칙·직업 프리셋을 학습하는 소형 나이브 베이즈 모델. 근거가 부족하면 추천하지 않음
  - 코칭: 선택한 날 또는 최근 7일의 통계 기반 요약
- **개인 모델 (선택)** — 설정에서 서비스를 고르고 모델을 입력하거나 서버에서 목록을 불러옴

  | 서비스 | API 키 | 기본 주소 |
  |---|---|---|
  | Claude (Anthropic) | 필요 | 고정 |
  | GPT (OpenAI) | 필요 | 고정 |
  | Ollama | 선택 | `http://localhost:11434/v1` |
  | LM Studio | 선택 | `http://localhost:1234/v1` |
  | 직접 입력 (OpenAI 호환) | 선택 | 직접 입력 |

  - 유료 서비스의 요금은 본인 계정에 청구됨. localhost가 아닌 서버는 https만 허용
- 개인 모델에는 앱 이름·도메인·집계 통계만 전송하며 창 제목과 전체 URL은 보내지 않음. API 키는 Windows 자격 증명 관리자에 서버별로 저장
- **전송 내용 보기** — 개인 모델 사용 시, 보내기 전에 받는 주소·모델·데이터·지침을 확인 (열기만 해서는 전송되지 않음)
- **분석 대기** — 경과 시간 표시와 취소 (화면을 벗어나도 취소되고 연결을 끊음. 이미 전송된 데이터는 되돌릴 수 없으며 유료 서비스는 요금이 청구될 수 있음)
- 실패하거나 취소하면 **내장 분석으로 보기**를 선택할 수 있음 (자동 전환하지 않으며 설정은 유지)
- 추천은 수락해야 규칙에 반영됨
- 내장 분류 모델 정확도 확인: `python -m time_manager.local_model <복호화된 activity.sqlite3 경로>`

### 진단
- 진단 실행, 로그 내보내기, Google Forms 문제 신고 링크 내장

---

## 스크린샷

<table>
<tr>
<td><img src="docs/screenshots/dashboard.png" width="320" alt="대시보드"/></td>
<td><img src="docs/screenshots/report.png" width="320" alt="리포트"/></td>
<td><img src="docs/screenshots/rules.png" width="320" alt="규칙 · 분류 제안"/></td>
</tr>
<tr>
<td align="center">대시보드</td>
<td align="center">리포트</td>
<td align="center">규칙 · 분류 제안</td>
</tr>
</table>

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 데스크탑 셸 | Python 3.12+, pywebview |
| UI | React 19, TypeScript, Vite 8 |
| 데이터 저장 | SQLite (`activity.sqlite3`) |
| 암호화 | cryptography (Fernet), keyring |
| Windows 플랫폼 | uiautomation, pystray, winotify, Pillow |
| 테스트 | pytest, Vitest 3, React Testing Library |
| 패키징 | PyInstaller + Inno Setup |

---

## 프로젝트 구조

```
time-manager/
├── main.py                    # 진입점
├── rules.json                 # 기본 분류 규칙
├── requirements.txt
├── time_manager.spec          # PyInstaller 빌드 설정
├── version_info.txt           # exe 버전 메타데이터
├── time_manager/               # Python 패키지 (부트스트랩, 활동 추적, 저장, 분류 규칙, React↔Python API 브릿지 등)
├── webui/                      # React 프론트엔드 (컴포넌트, 훅, API 래퍼)
├── installer/                  # Inno Setup 인스톨러 스크립트
└── tests/                      # pytest 테스트
```
