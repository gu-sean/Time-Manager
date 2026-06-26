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

### 진단
- 진단 실행, 로그 내보내기, Google Forms 문제 신고 링크 내장

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
│
├── time_manager/              # Python 패키지
│   ├── app.py                 # 부트스트랩 + 라이프사이클 (decrypt/encrypt)
│   ├── webapp.py              # pywebview 창 설정
│   ├── tracker.py             # 활동 추적 루프
│   ├── storage.py             # SQLite ActivityStore
│   ├── rules.py               # 분류 규칙 엔진
│   ├── settings.py            # 사용자 설정 모델
│   ├── backup.py              # 백업·복원 (ZipBomb 방어 포함)
│   ├── db_crypto.py           # DB 암호화-at-rest (Fernet)
│   ├── updater.py             # GitHub Releases 업데이트 확인
│   ├── startup.py             # Windows 시작 프로그램 등록
│   ├── diagnostics.py         # 로컬 상태 진단
│   ├── models.py              # 데이터 모델
│   ├── paths.py               # 경로 관리 (개발/패키지 모드)
│   └── webapi/                # React ↔ Python 브릿지 (Mixin 구조)
│       ├── __init__.py        # WebApi 조합 클래스
│       ├── _shared.py         # WebApiBase (타입 체커용)
│       ├── dashboard.py
│       ├── inbox.py
│       ├── report.py
│       ├── review.py
│       ├── rules.py
│       ├── settings.py
│       └── backup.py
│
├── webui/                     # React 프론트엔드
│   └── src/
│       ├── api.ts             # pywebview API 래퍼 함수
│       ├── types.ts           # 공유 TypeScript 타입
│       ├── App.tsx            # 루트 컴포넌트
│       ├── components/        # UI 컴포넌트
│       │   ├── Dashboard.tsx
│       │   ├── Inbox.tsx
│       │   ├── Report.tsx
│       │   ├── Review.tsx
│       │   ├── Rules.tsx
│       │   ├── Settings.tsx
│       │   ├── Sidebar.tsx
│       │   ├── Header.tsx
│       │   ├── FocusTimer.tsx
│       │   └── Toggle.tsx
│       └── hooks/             # 커스텀 훅
│           ├── useInboxHandlers.ts
│           ├── useRulesHandlers.ts
│           ├── useReportHandlers.ts
│           └── useSettingsHandlers.ts
```