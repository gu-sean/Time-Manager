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
  addRule,
  applyPreset,
  changeDay,
  deleteEvent,
  deleteRule,
  exportBackup,
  exportCsv,
  exportCsvPeriod,
  getDashboard,
  getInbox,
  getReport,
  getReportRange,
  getReview,
  getRules,
  getSettings,
  restoreBackup,
  restoreDeletedEvent,
  returnToToday,
  runDiagnostics,
  saveSettings,
  updateRule,
  setTheme,
  setProfile,
  toggleAutoBackup,
  toggleExcludeSelf,
  toggleNotifications,
  toggleTracking,
  waitForApi,
} from './api';
import type { DashboardData, InboxData, ReportData, ReviewData, RulesData, SettingsData } from './types';

const PAGE_META: Record<string, { title: string; sub: string }> = {
  dashboard: { title: '대시보드', sub: '오늘의 흐름' },
  inbox: { title: '정리함', sub: '활동 정리' },
  review: { title: '회고', sub: '일간 리뷰' },
  rules: { title: '규칙', sub: '분류 규칙' },
  report: { title: '리포트', sub: '통계 리포트' },
  settings: { title: '개인화', sub: '설정' },
};

const POLL_MS = 5000;

function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [inbox, setInbox] = useState<InboxData | null>(null);
  const [review, setReview] = useState<ReviewData | null>(null);
  const [rules, setRules] = useState<RulesData | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [settingsMessage, setSettingsMessage] = useState('');
  const pollRef = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    const data = await getDashboard();
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
    if (!settingsMessage) return undefined;
    const timeout = window.setTimeout(() => setSettingsMessage(''), 2800);
    return () => window.clearTimeout(timeout);
  }, [settingsMessage]);

  useEffect(() => {
    if (activePage === 'inbox' && !inbox) {
      waitForApi().then(() => getInbox().then(setInbox));
    }
    if (activePage === 'review' && !review) {
      waitForApi().then(() => getReview().then(setReview));
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

  const refreshSecondaryTabs = useCallback(async () => {
    if (activePage === 'inbox') setInbox(await getInbox());
    if (activePage === 'review') setReview(await getReview());
  }, [activePage]);

  const handlePrevDay = useCallback(async () => {
    setDashboard(await changeDay(-1));
    await refreshSecondaryTabs();
  }, [refreshSecondaryTabs]);
  const handleNextDay = useCallback(async () => {
    setDashboard(await changeDay(1));
    await refreshSecondaryTabs();
  }, [refreshSecondaryTabs]);
  const handleToday = useCallback(async () => {
    setDashboard(await returnToToday());
    await refreshSecondaryTabs();
  }, [refreshSecondaryTabs]);
  const handleToggleFocus = useCallback(async (enabled: boolean) => {
    setDashboard(await toggleNotifications(enabled));
    setSettings(await getSettings());
    setSettingsMessage(enabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, []);
  const handleHeaderToggleNotifications = useCallback(async () => {
    const nextEnabled = !notificationsEnabled;
    setDashboard(await toggleNotifications(nextEnabled));
    setSettings(await getSettings());
    setSettingsMessage(nextEnabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, [notificationsEnabled]);
  const handleToggleTheme = useCallback(async () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setSettings(await setTheme(nextTheme));
    setSettingsMessage(nextTheme === 'dark' ? '다크 모드를 켰습니다.' : '라이트 모드로 변경했습니다.');
  }, [theme]);
  const handleToggleTracking = useCallback(async () => {
    setDashboard(await toggleTracking());
  }, []);

  const handleSearch = useCallback(async (query: string, category: string | null) => {
    setInbox(await getInbox(query, category));
  }, []);
  const handleClearSearch = useCallback(async () => {
    setInbox(await getInbox());
  }, []);
  const handleDelete = useCallback(async (eventId: number) => {
    setInbox(await deleteEvent(eventId));
  }, []);
  const handleRestore = useCallback(async () => {
    setInbox(await restoreDeletedEvent());
  }, []);

  const handleAddRule = useCallback(async (ruleType: string, category: string, value: string) => {
    setRules(await addRule(ruleType, category, value));
  }, []);
  const handleUpdateRule = useCallback(
    async (oldKey: string, oldValue: string, ruleType: string, category: string, value: string) => {
      setRules(await updateRule(oldKey, oldValue, ruleType, category, value));
    },
    [],
  );
  const handleDeleteRule = useCallback(async (key: string, value: string) => {
    setRules(await deleteRule(key, value));
  }, []);

  const handleChangePeriod = useCallback(async (period: string) => {
    setReport(await getReport(period));
  }, []);
  const handleChangeRange = useCallback(async (startIso: string, endIso: string) => {
    setReport(await getReportRange(startIso, endIso));
  }, []);

  const handleSaveSettings = useCallback(async (payload: Record<string, unknown>) => {
    const result = await saveSettings(payload);
    setSettings(result);
    setSettingsMessage(result.error ? '' : '저장했습니다.');
  }, []);
  const handleToggleExcludeSelf = useCallback(async (enabled: boolean) => {
    setSettings(await toggleExcludeSelf(enabled));
    setSettingsMessage(enabled ? '시간 관리자 앱을 기록에서 제외합니다.' : '시간 관리자 앱도 기록합니다.');
  }, []);
  const handleToggleAutoBackup = useCallback(async (enabled: boolean) => {
    setSettings(await toggleAutoBackup(enabled));
    setSettingsMessage(enabled ? '자동 백업을 켰습니다.' : '자동 백업을 껐습니다.');
  }, []);
  const handleToggleSettingsNotifications = useCallback(async (enabled: boolean) => {
    setDashboard(await toggleNotifications(enabled));
    setSettings(await getSettings());
    setSettingsMessage(enabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, []);
  const handleSetTheme = useCallback(async (nextTheme: 'light' | 'dark') => {
    setSettings(await setTheme(nextTheme));
    setSettingsMessage(nextTheme === 'dark' ? '다크 모드를 켰습니다.' : '라이트 모드로 변경했습니다.');
  }, []);
  const handleSetProfile = useCallback(async (profile: string) => {
    setSettings(await setProfile(profile));
    setSettingsMessage('직업 프리셋을 선택했습니다.');
  }, []);
  const handleApplyPreset = useCallback(async () => {
    setSettings(await applyPreset());
    setSettingsMessage('프리셋 후보 규칙을 적용했습니다.');
  }, []);
  const handleRunDiagnostics = useCallback(async () => {
    setSettings(await runDiagnostics());
  }, []);
  const handleExportCsv = useCallback(async () => {
    const result = await exportCsv();
    if (result.message) setSettingsMessage(result.message);
  }, []);
  const handleExportCsvPeriod = useCallback(async (period: string) => {
    const result = await exportCsvPeriod(period);
    if (result.message) setSettingsMessage(result.message);
  }, []);
  const handleExportBackup = useCallback(async () => {
    const result = await exportBackup();
    if (result.message) setSettingsMessage(result.message);
  }, []);
  const handleRestoreBackup = useCallback(async () => {
    const result = await restoreBackup();
    if (result.message) setSettingsMessage(result.message);
    if (result.dailyGoalMinutes !== undefined) setSettings(result as SettingsData);
  }, []);

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
              onSearch={handleSearch}
              onClearSearch={handleClearSearch}
              onDelete={handleDelete}
              onRestore={handleRestore}
            />
          )}
          {activePage === 'review' && review && <Review data={review} />}
          {activePage === 'rules' && rules && (
            <Rules data={rules} onAdd={handleAddRule} onUpdate={handleUpdateRule} onDelete={handleDeleteRule} />
          )}
          {activePage === 'report' && report && <Report data={report} onChangePeriod={handleChangePeriod} onChangeRange={handleChangeRange} />}
          {activePage === 'settings' && settings && (
            <SettingsPage
              key={settingsFormKey}
              data={settings}
              message={settingsMessage}
              onSave={handleSaveSettings}
              onToggleExcludeSelf={handleToggleExcludeSelf}
              onToggleAutoBackup={handleToggleAutoBackup}
              onToggleNotifications={handleToggleSettingsNotifications}
              onToggleTheme={handleSetTheme}
              onSetProfile={handleSetProfile}
              onApplyPreset={handleApplyPreset}
              onRunDiagnostics={handleRunDiagnostics}
              onExportCsv={handleExportCsv}
              onExportCsvPeriod={handleExportCsvPeriod}
              onExportBackup={handleExportBackup}
              onRestoreBackup={handleRestoreBackup}
            />
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
