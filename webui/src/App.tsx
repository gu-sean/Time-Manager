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
import {
  getDashboard,
  getInbox,
  getReport,
  getReview,
  getRules,
  getSettings,
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
  dashboard: { title: '대시보드', sub: '오늘의 흐름' },
  inbox: { title: '정리함', sub: '활동 정리' },
  review: { title: '회고', sub: '일간 리뷰' },
  rules: { title: '규칙', sub: '분류 규칙' },
  report: { title: '리포트', sub: '통계 리포트' },
  settings: { title: '개인화', sub: '설정' },
};

const POLL_MS = 5000;

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
  const pollRef = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    const today = localDateIso();
    if (selectedDayRef.current !== today && selectedDayRef.current === prevDayRef.current) {
      selectedDayRef.current = today;
      setSelectedDay(today);
      setToast('날짜가 변경되었습니다.');
    }
    prevDayRef.current = today;
    const data = await getDashboard(selectedDayRef.current);
    setDashboard(data);
  }, []);

  const theme = settings?.theme ?? 'light';
  const notificationsEnabled = settings?.notificationsEnabled ?? dashboard?.focusMode.enabled ?? true;

  useEffect(() => {
    let cancelled = false;
    waitForApi().then(() => {
      if (!cancelled) {
        refresh();
        getSettings().then((result) => {
          if (!cancelled) setSettings(result);
        });
      }
    });
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
    const timeout = window.setTimeout(() => setToast(''), 2800);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  useEffect(() => {
    if (activePage === 'inbox' && !inbox) {
      waitForApi().then(() => getInbox('', null, selectedDayRef.current).then(setInbox));
    }
    if (activePage === 'review' && !review) {
      waitForApi().then(() => getReview(selectedDayRef.current).then(setReview));
    }
    if (activePage === 'rules' && !rules) {
      waitForApi().then(() => getRules().then(setRules));
    }
    if (activePage === 'report' && !report) {
      waitForApi().then(() => getReport().then(setReport));
    }
    if (activePage === 'settings' && !settings) {
      waitForApi().then(() => getSettings().then(setSettings));
    }
  }, [activePage, inbox, review, rules, report, settings]);

  const navigateDay = useCallback(async (newDay: string) => {
    selectedDayRef.current = newDay;
    setSelectedDay(newDay);
    setDashboard(await getDashboard(newDay));
    if (activePage === 'inbox') setInbox(await getInbox('', null, newDay));
    if (activePage === 'review') setReview(await getReview(newDay));
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

  const handleToggleFocus = useCallback(async (enabled: boolean) => {
    setDashboard(await toggleNotifications(enabled));
    setSettings(await getSettings());
    setToast(enabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, []);

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

  const handleToggleTracking = useCallback(async () => {
    setDashboard(await toggleTracking());
  }, []);

  const inboxHandlers = useInboxHandlers(selectedDayRef, setInbox);
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

  const meta = PAGE_META[activePage] ?? PAGE_META.dashboard;
  const settingsFormKey = settings
    ? [
        settings.dailyGoalMinutes,
        settings.weeklyGoalMinutes,
        settings.unproductiveLimitMinutes,
        settings.workStartHour,
        settings.workEndHour,
        settings.retentionDays,
      ].join(':')
    : 'settings';

  return (
    <div className={`tm-shell ${theme === 'dark' ? 'dark' : 'light'}`}>
      <Sidebar
        activePage={activePage}
        onSelectPage={setActivePage}
        tracking={dashboard?.tracking ?? true}
        dashboard={dashboard}
        onToggleTracking={handleToggleTracking}
      />
      <main className="tm-main">
        <Header
          title={meta.title}
          subtitle={meta.sub}
          dateLabel={dashboard?.dateLabel ?? '오늘'}
          viewingToday={dashboard?.viewingToday ?? true}
          notificationsEnabled={notificationsEnabled}
          theme={theme}
          onPrevDay={handlePrevDay}
          onNextDay={handleNextDay}
          onToday={handleToday}
          onToggleNotifications={handleHeaderToggleNotifications}
          onToggleTheme={handleToggleTheme}
        />
        <div className="tm-scroll">
          {activePage === 'dashboard' && dashboard && (
            <Dashboard data={dashboard} onToggleFocus={handleToggleFocus} />
          )}
          {activePage === 'inbox' && inbox && (
            <Inbox
              data={inbox}
              onSearch={inboxHandlers.handleSearch}
              onClearSearch={inboxHandlers.handleClearSearch}
              onDelete={inboxHandlers.handleDelete}
              onRestore={inboxHandlers.handleRestore}
            />
          )}
          {activePage === 'review' && review && <Review data={review} />}
          {activePage === 'rules' && rules && (
            <Rules
              data={rules}
              onAdd={rulesHandlers.handleAddRule}
              onUpdate={rulesHandlers.handleUpdateRule}
              onDelete={rulesHandlers.handleDeleteRule}
            />
          )}
          {activePage === 'report' && report && (
            <Report
              data={report}
              onChangePeriod={reportHandlers.handleChangePeriod}
              onChangeRange={reportHandlers.handleChangeRange}
              onExportCsv={reportHandlers.handleExportCsvReport}
            />
          )}
          {activePage === 'settings' && settings && (
            <SettingsPage
              key={settingsFormKey}
              data={settings}
              onSave={settingsHandlers.handleSaveSettings}
              onToggleExcludeSelf={settingsHandlers.handleToggleExcludeSelf}
              onToggleAutoBackup={settingsHandlers.handleToggleAutoBackup}
              onToggleStartup={settingsHandlers.handleToggleStartup}
              onToggleNotifications={settingsHandlers.handleToggleSettingsNotifications}
              onToggleTheme={settingsHandlers.handleSetTheme}
              onSetProfile={settingsHandlers.handleSetProfile}
              onApplyPreset={settingsHandlers.handleApplyPreset}
              onRunDiagnostics={settingsHandlers.handleRunDiagnostics}
              onCheckUpdate={settingsHandlers.handleCheckUpdate}
              onInstallUpdate={settingsHandlers.handleInstallUpdate}
              onExportLogs={settingsHandlers.handleExportLogs}
              onExportCsv={settingsHandlers.handleExportCsv}
              onExportCsvPeriod={settingsHandlers.handleExportCsvPeriod}
              onExportBackup={settingsHandlers.handleExportBackup}
              onRestoreBackup={settingsHandlers.handleRestoreBackup}
            />
          )}
        </div>
      </main>
      {toast && <div className="tm-toast">{toast}</div>}
    </div>
  );
}

export default App;
