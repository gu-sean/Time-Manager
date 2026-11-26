import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import Inbox from './components/Inbox';
import Review from './components/Review';
import Rules from './components/Rules';
import Report from './components/Report';
import SettingsPage from './components/Settings';
import ErrorBoundary from './components/ErrorBoundary';
import StatusBanners from './components/StatusBanners';
import { describeError } from './errors';
import type { SettingsTab } from './components/Settings';
import {
  getDashboard,
  getInbox,
  getReport,
  getAiCoaching,
  getReview,
  getRules,
  getSettings,
  pauseTracking,
  setTheme,
  toggleNotifications,
  toggleTracking,
  waitForApi,
} from './api';
import type { DashboardData, InboxData, ReportData, ReviewData, RulesData, SettingsData } from './types';
import { useInboxHandlers } from './hooks/useInboxHandlers';
import { useReportHandlers } from './hooks/useReportHandlers';
import { useRulesHandlers } from './hooks/useRulesHandlers';
import { useSettingsHandlers } from './hooks/useSettingsHandlers';

const PAGE_META: Record<string, { title: string; sub: string }> = {
  dashboard: { title: '대시보드', sub: '하루의 흐름' },
  inbox: { title: '정리함', sub: '활동 정리' },
  review: { title: '회고', sub: '일간 리뷰' },
  rules: { title: '규칙', sub: '분류 규칙' },
  report: { title: '리포트', sub: '통계 리포트' },
  settings: { title: '개인화', sub: '설정' },
};

const POLL_MS = 5000;
// 하루 단위 화면에만 날짜 선택기 표시
const DATE_PAGES = new Set(['dashboard', 'inbox', 'review']);

function localDateIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function shiftDateIso(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  const shifted = new Date(y, m - 1, d + days);
  return `${shifted.getFullYear()}-${String(shifted.getMonth() + 1).padStart(2, '0')}-${String(shifted.getDate()).padStart(2, '0')}`;
}

function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [selectedDay, setSelectedDay] = useState<string>(localDateIso);
  const selectedDayRef = useRef<string>(selectedDay);
  const prevDayRef = useRef<string>(selectedDay);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [inbox, setInbox] = useState<InboxData | null>(null);
  const [review, setReview] = useState<ReviewData | null>(null);
  const [rules, setRules] = useState<RulesData | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [toast, setToast] = useState('');
  // 설정 화면이 저장 후 다시 마운트되므로 여기서 보관
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('general');
  const pollRef = useRef<number | undefined>(undefined);
  const [failure, setFailure] = useState('');
  const [connectionLost, setConnectionLost] = useState(false);
  const [loadFailed, setLoadFailed] = useState<Record<string, boolean>>({});
  const [seenNotices, setSeenNotices] = useState<string[]>([]);
  const refreshFailures = useRef(0);

  const refresh = useCallback(async () => {
    try {
      await waitForApi();
      const today = localDateIso();
      if (selectedDayRef.current !== today && selectedDayRef.current === prevDayRef.current) {
        selectedDayRef.current = today;
        setSelectedDay(today);
        setToast('날짜가 변경되었습니다.');
      }
      prevDayRef.current = today;
      const day = selectedDayRef.current;
      const data = await getDashboard(day);
      refreshFailures.current = 0;
      setConnectionLost(false);
      if (selectedDayRef.current === day) setDashboard(data); // 그사이 사용자가 다른 날짜로 이동했을 수 있음
    } catch (error) {
      console.error('refresh failed', error);
      // 갱신 한 번 놓친 것은 경고하지 않음
      refreshFailures.current += 1;
      if (refreshFailures.current >= 2) setConnectionLost(true);
    }
  }, []);

  // 버튼에서 시작해 아무도 처리하지 않은 오류는 여기서 알림 (조용히 사라지지 않게)
  useEffect(() => {
    const report = (event: PromiseRejectionEvent) => {
      event.preventDefault();
      console.error('action failed', event.reason);
      setToast(''); // 실패 안내 옆에 성공 메시지가 남지 않게 함
      setFailure(describeError(event.reason));
      // 백엔드는 디스크 상태를 유지하므로 그 값을 다시 표시
      getSettings().then(setSettings).catch(() => undefined);
    };
    window.addEventListener('unhandledrejection', report);
    return () => window.removeEventListener('unhandledrejection', report);
  }, []);

  const theme = settings?.theme ?? 'light';
  const notificationsEnabled = settings?.notificationsEnabled ?? true;

  useEffect(() => {
    let cancelled = false;
    // 첫 로드 후 몇 초마다 갱신
    void Promise.resolve().then(refresh);
    waitForApi()
      .then(getSettings)
      .then((result) => {
        if (!cancelled) setSettings(result);
      })
      .catch((error) => console.error('settings failed to load', error));
    pollRef.current = window.setInterval(refresh, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(pollRef.current);
    };
  }, [refresh]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = window.setTimeout(() => setToast(''), Math.max(2800, toast.length * 100));
    return () => window.clearTimeout(timeout);
  }, [toast]);

  // 화면에 처음 들어갈 때 데이터 로드, 실패하면 다시 시도 제공
  useEffect(() => {
    if (loadFailed[activePage]) return;
    const day = selectedDayRef.current;
    const loaders: Record<string, (() => Promise<void>) | false> = {
      inbox: !inbox && (async () => setInbox(await getInbox('', null, day))),
      review: !review && (async () => setReview(await getReview(day))),
      rules: !rules && (async () => setRules(await getRules())),
      report: !report && (async () => setReport(await getReport())),
      settings: !settings && (async () => setSettings(await getSettings())),
    };
    const load = loaders[activePage];
    if (!load) return;
    waitForApi()
      .then(load)
      .catch((error) => {
        console.error(`${activePage} failed to load`, error);
        setLoadFailed((failed) => ({ ...failed, [activePage]: true }));
      });
  }, [activePage, inbox, review, rules, report, settings, loadFailed]);

  // 다시 시도는 처음부터: 화면을 깨뜨린 데이터를 다시 보여주지 않음
  const retryPage = useCallback(() => {
    setLoadFailed((failed) => ({ ...failed, [activePage]: false }));
    const discard: Record<string, () => void> = {
      dashboard: () => setDashboard(null),
      inbox: () => setInbox(null),
      review: () => setReview(null),
      rules: () => setRules(null),
      report: () => setReport(null),
      settings: () => setSettings(null),
    };
    discard[activePage]?.();
    if (activePage === 'dashboard') void refresh();
  }, [activePage, refresh]);

  const navigateDay = useCallback(async (newDay: string) => {
    selectedDayRef.current = newDay;
    setSelectedDay(newDay);
    // 빠르게 여러 번 눌러도 이전 날짜의 응답이 최신 화면을 덮지 않게 함
    const current = () => selectedDayRef.current === newDay;
    // 날짜를 쓰는 다른 화면은 다음에 열 때 다시 로드
    if (activePage !== 'inbox') setInbox(null);
    if (activePage !== 'review') setReview(null);
    const nextDashboard = await getDashboard(newDay);
    if (current()) setDashboard(nextDashboard);
    if (activePage === 'inbox') {
      const next = await getInbox('', null, newDay);
      if (current()) setInbox(next);
    }
    if (activePage === 'review') {
      const next = await getReview(newDay);
      if (current()) setReview(next);
    }
  }, [activePage]);

  const handlePrevDay = useCallback(async () => {
    await navigateDay(shiftDateIso(selectedDay, -1));
  }, [selectedDay, navigateDay]);

  const handleNextDay = useCallback(async () => {
    const today = localDateIso();
    const next = shiftDateIso(selectedDay, 1);
    await navigateDay(next <= today ? next : today);
  }, [selectedDay, navigateDay]);

  const handleToday = useCallback(async () => {
    await navigateDay(localDateIso());
  }, [navigateDay]);

  const handleHeaderToggleNotifications = useCallback(async () => {
    const nextEnabled = !notificationsEnabled;
    setDashboard(await toggleNotifications(nextEnabled));
    setSettings(await getSettings());
    setToast(nextEnabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, [notificationsEnabled]);

  const handleToggleTheme = useCallback(async () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setSettings(await setTheme(nextTheme));
    setToast(nextTheme === 'dark' ? '다크 모드를 켰습니다.' : '라이트 모드로 변경했습니다.');
  }, [theme]);

  const handlePause = useCallback(async (minutes: number | null) => {
    setDashboard(await pauseTracking(minutes));
    setToast(minutes ? `${minutes >= 60 ? `${minutes / 60}시간` : `${minutes}분`} 동안 기록을 멈춰요.` : '기록을 멈췄어요. 스위치를 켜면 다시 기록해요.');
  }, []);

  const handleToggleTracking = useCallback(async () => {
    setDashboard(await toggleTracking());
  }, []);

  // 회고·리포트는 방문 단위 캐시 → 기록이 바뀌면 버림
  const handleRecordsChanged = useCallback(() => {
    setReview(null);
    setReport(null);
    refresh();
  }, [refresh]);

  const inboxHandlers = useInboxHandlers(selectedDayRef, inbox, setInbox, handleRecordsChanged, setToast);
  const rulesHandlers = useRulesHandlers(setRules, setToast);
  const reportHandlers = useReportHandlers(report, setReport, setToast);
  const settingsHandlers = useSettingsHandlers({
    setSettings,
    setDashboard,
    setInbox,
    setReview,
    setRules,
    setReport,
    setToast,
    selectedDayRef,
  });

  const externalAi = !!settings && settings.aiProvider !== 'local';
  const pageData: Record<string, unknown> = { dashboard, inbox, review, rules, report, settings };
  const meta = PAGE_META[activePage] ?? PAGE_META.dashboard;

  return (
    <div className={`tm-shell ${theme === 'dark' ? 'dark' : 'light'}`}>
      <Sidebar
        activePage={activePage}
        onSelectPage={setActivePage}
        tracking={dashboard?.tracking ?? false}
        dashboard={dashboard}
        onToggleTracking={handleToggleTracking}
        onPause={handlePause}
        appVersion={settings?.appVersion}
      />
      <main className="tm-main">
        <Header
          title={meta.title}
          subtitle={
            activePage === 'dashboard' && dashboard ? `${meta.sub} · ▲▼ ${dashboard.comparedWith} 대비` : meta.sub
          }
          dateLabel={dashboard?.dateLabel ?? '오늘'}
          viewingToday={dashboard?.viewingToday ?? true}
          notificationsEnabled={notificationsEnabled}
          theme={theme}
          showDate={DATE_PAGES.has(activePage)}
          onPrevDay={handlePrevDay}
          onNextDay={handleNextDay}
          onToday={handleToday}
          onToggleNotifications={handleHeaderToggleNotifications}
          onToggleTheme={handleToggleTheme}
        />
        <div className="tm-scroll">
          <StatusBanners
            failure={failure}
            onDismissFailure={() => setFailure('')}
            connectionLost={connectionLost}
            problem={dashboard?.problem ?? ''}
            notices={(dashboard?.notices ?? []).filter((notice) => !seenNotices.includes(notice))}
            onDismissNotice={(notice) => setSeenNotices((seen) => [...seen, notice])}
          />
          {!pageData[activePage] &&
            (loadFailed[activePage] || (activePage === 'dashboard' && connectionLost) ? (
              <div className="tm-card tm-state-card" role="alert">
                <div className="tm-card-title">화면을 불러오지 못했어요</div>
                <div>잠시 후 다시 시도해주세요. 계속 반복되면 앱을 다시 실행해보세요.</div>
                <button className="tm-btn-small tm-btn-primary" type="button" onClick={retryPage}>
                  다시 시도
                </button>
              </div>
            ) : (
              <div className="tm-empty-row" role="status">불러오는 중…</div>
            ))}
          {/* 화면별 key: 깨진 화면을 벗어나면 오류 해제 */}
          <ErrorBoundary key={activePage} onRetry={retryPage}>
          {activePage === 'dashboard' && dashboard && (
            <Dashboard data={dashboard} />
          )}
          {activePage === 'inbox' && inbox && (
            <Inbox
              data={inbox}
              onSearch={inboxHandlers.handleSearch}
              onClearSearch={inboxHandlers.handleClearSearch}
              onDelete={inboxHandlers.handleDelete}
              onRestore={inboxHandlers.handleRestore}
              onReclassify={inboxHandlers.handleReclassify}
              onAddRule={inboxHandlers.handleAddRule}
              onDeleteTarget={inboxHandlers.handleDeleteTarget}
              onAddManual={inboxHandlers.handleAddManual}
            />
          )}
          {activePage === 'review' && review && (
            <Review
              data={review}
              external={externalAi}
              dateIso={selectedDay}
              onGetCoaching={getAiCoaching}
            />
          )}
          {activePage === 'rules' && rules && (
            <Rules
              data={rules}
              onAdd={rulesHandlers.handleAddRule}
              onUpdate={rulesHandlers.handleUpdateRule}
              onDelete={rulesHandlers.handleDeleteRule}
              onGetSuggestions={rulesHandlers.handleGetRuleSuggestions}
              onApplySuggestion={rulesHandlers.handleApplyRuleSuggestion}
              external={externalAi}
              onGetAiSuggestions={rulesHandlers.handleGetAiSuggestions}
              onReapplied={(message) => {
                setInbox(null);
                handleRecordsChanged();
                setToast(message);
              }}
            />
          )}
          {activePage === 'report' && report && (
            <Report
              data={report}
              onChangePeriod={reportHandlers.handleChangePeriod}
              onChangeRange={reportHandlers.handleChangeRange}
              onExportCsv={reportHandlers.handleExportCsvReport}
              external={externalAi}
            />
          )}
          {activePage === 'settings' && settings && (
            <SettingsPage
              data={settings}
              tab={settingsTab}
              onTabChange={setSettingsTab}
              onSave={settingsHandlers.handleSaveSettings}
              onToggleAutoBackup={settingsHandlers.handleToggleAutoBackup}
              onToggleStartup={settingsHandlers.handleToggleStartup}
              onSaveTracking={settingsHandlers.handleSaveTracking}
              onToggleNotifications={settingsHandlers.handleToggleSettingsNotifications}
              onToggleTheme={settingsHandlers.handleSetTheme}
              onSetProfile={settingsHandlers.handleSetProfile}
              onApplyPreset={settingsHandlers.handleApplyPreset}
              onCreatePreset={settingsHandlers.handleCreatePreset}
              onUpdatePreset={settingsHandlers.handleUpdatePreset}
              onDeletePreset={settingsHandlers.handleDeletePreset}
              onRunDiagnostics={settingsHandlers.handleRunDiagnostics}
              onCheckUpdate={settingsHandlers.handleCheckUpdate}
              onInstallUpdate={settingsHandlers.handleInstallUpdate}
              onExportLogs={settingsHandlers.handleExportLogs}
              onExportCsv={settingsHandlers.handleExportCsv}
              onExportCsvPeriod={settingsHandlers.handleExportCsvPeriod}
              onExportBackup={settingsHandlers.handleExportBackup}
              onRestoreBackup={settingsHandlers.handleRestoreBackup}
              onSaveAiSettings={settingsHandlers.handleSaveAiSettings}
              onSetAiApiKey={settingsHandlers.handleSetAiApiKey}
              onClearAiApiKey={settingsHandlers.handleClearAiApiKey}
              onTestAiConnection={settingsHandlers.handleTestAiConnection}
              onListAiModels={settingsHandlers.handleListAiModels}
              onAddAiExclusion={settingsHandlers.handleAddAiExclusion}
              onRemoveAiExclusion={settingsHandlers.handleRemoveAiExclusion}
              onRecordsDeleted={(message) => {
                setInbox(null);
                handleRecordsChanged();
                setToast(message);
              }}
            />
          )}
          </ErrorBoundary>
        </div>
      </main>
      {/* 화면 낭독기가 새 메시지를 읽도록 항상 렌더링 */}
      <div role="status" aria-live="polite">
        {toast && <div className="tm-toast">{toast}</div>}
      </div>
    </div>
  );
}

export default App;
