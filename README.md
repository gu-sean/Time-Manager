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
- Rules 탭에서 JSON 편집 없이 추가·삭제·필터 가능

### 활동 인박스
- 기록된 활동 카테고리 수정 및 규칙으로 저장
- 최근 7일간 반복된 중립 항목 추천 및 일괄 분류
- 앱·URL·창 제목 키워드 검색 (최근 30일)

### 데일리 리뷰
- 선택 날짜의 생산적 활동·최대 방해 요소·미분류 항목 요약
- 세션·전환 횟수 기반 흐름 분석
- 25분 이상 집중 블록 감지

### 리포트
- 최근 7일 / 30일 / 이번 달 생산성 통계
- 24시간 활동 차트 (생산적·비생산적·중립 시간 누적)
- 일별 생산성 점수 추세선
- 취약 시간대·반복 방해 요소·요일 패턴 분석

### 개인화 및 설정
- 역할별 스타터 프리셋 (개발자·학생·사무직·크리에이터 등)
- 일일 생산 목표 / 비생산 시간 상한 설정
- 데이터 보존 기간, 자동 백업, CSV 내보내기
- 언어 전환 (한국어 / 영어)

### 시스템 트레이
- 창 닫기 → 트레이로 최소화
- 트레이 메뉴에서 대시보드 열기 / 추적 일시정지·재개 / 종료

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 데스크탑 셸 | Python 3, pywebview |
| UI | React 18, TypeScript, Vite |
| 데이터 저장 | SQLite (`activity.sqlite3`) |
| Windows 플랫폼 | uiautomation, pystray, winotify, Pillow |
| 패키징 | PyInstaller |
| 테스트 | pytest |

---

## 디렉토리 구조

```
time-manager/
├── main.py                  # 진입점
├── rules.json               # 기본 분류 규칙
├── requirements.txt
├── pytest.ini
├── time_manager.spec        # PyInstaller 빌드 (TimeManager.exe)
├── time_manager_webview.spec# PyInstaller 빌드 (TimeManagerWeb.exe)
├── version_info.txt         # 실행 파일 버전 메타데이터
│
├── time_manager/            # Python 패키지
│   ├── app.py               # 부트스트랩 및 webview 진입점
│   ├── webapi.py            # React ↔ Python 브릿지 API
│   ├── webapp.py            # pywebview 창 설정
│   ├── tracker.py           # 활동 추적 루프
│   ├── storage.py           # SQLite 저장소
│   ├── rules.py             # 분류 규칙 엔진
│   ├── settings.py          # 사용자 설정
│   ├── backup.py            # 백업·복원
│   ├── notifications.py     # Windows 알림
│   ├── diagnostics.py       # 로컬 상태 진단
│   ├── formatting.py        # 시간 포맷 유틸
│   ├── i18n.py              # 다국어 지원
│   ├── models.py            # 데이터 모델
│   ├── paths.py             # 경로 관리 (개발/패키지 모드)
│   └── platforms/
│       └── windows.py       # Windows 포어그라운드·URL 추출
│
├── webui/                   # React 프론트엔드
│   └── src/
│       ├── api.ts           # Python 브릿지 호출
│       ├── types.ts         # 공유 타입 정의
│       ├── App.tsx
│       └── components/
│           ├── Dashboard.tsx
│           ├── Inbox.tsx
│           ├── Report.tsx
│           ├── Review.tsx
│           ├── Rules.tsx
│           ├── Settings.tsx
│           ├── Sidebar.tsx
│           ├── Header.tsx
│           ├── FocusTimer.tsx
│           └── Toggle.tsx
│
├── assets/                  # 아이콘 등 정적 리소스
```