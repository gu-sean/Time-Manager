import { useCallback } from 'react';
import type { RefObject } from 'react';
import {
  applyPreset,
  exportBackup,
  exportCsv,
  exportCsvPeriod,
  getDashboard,
  getSettings,
  restoreBackup,
  runDiagnostics,
  saveSettings,
  setProfile,
  setTheme,
  toggleAutoBackup,
  toggleExcludeSelf,
  toggleNotifications,
  toggleStartup,
} from '../api';
import type { DashboardData, InboxData, ReportData, ReviewData, RulesData, SettingsData } from '../types';

interface Setters {
  setSettings: (data: SettingsData) => void;
  setDashboard: (data: DashboardData) => void;
  setInbox: (data: InboxData | null) => void;
  setReview: (data: ReviewData | null) => void;
  setRules: (data: RulesData | null) => void;
  setReport: (data: ReportData | null) => void;
  setToast: (msg: string) => void;
  selectedDayRef: RefObject<string>;
}

export function useSettingsHandlers({
  setSettings,
  setDashboard,
  setInbox,
  setReview,
  setRules,
  setReport,
  setToast,
  selectedDayRef,
}: Setters) {
  const handleSaveSettings = useCallback(async (payload: Record<string, unknown>) => {
    const result = await saveSettings(payload);
    setSettings(result);
    setToast(result.error ? '' : '저장했습니다.');
  }, []);

  const handleToggleExcludeSelf = useCallback(async (enabled: boolean) => {
    setSettings(await toggleExcludeSelf(enabled));
    setToast(enabled ? '시간 관리자 앱을 기록에서 제외합니다.' : '시간 관리자 앱도 기록합니다.');
  }, []);

  const handleToggleAutoBackup = useCallback(async (enabled: boolean) => {
    setSettings(await toggleAutoBackup(enabled));
    setToast(enabled ? '자동 백업을 켰습니다.' : '자동 백업을 껐습니다.');
  }, []);

  const handleToggleStartup = useCallback(async (enabled: boolean) => {
    const result = await toggleStartup(enabled);
    setSettings(result);
    setToast(result.error ? '' : enabled ? '시작 시 자동 실행을 켰습니다.' : '시작 시 자동 실행을 껐습니다.');
  }, []);

  const handleToggleSettingsNotifications = useCallback(async (enabled: boolean) => {
    setDashboard(await toggleNotifications(enabled));
    setSettings(await getSettings());
    setToast(enabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, []);

  const handleSetTheme = useCallback(async (nextTheme: 'light' | 'dark') => {
    setSettings(await setTheme(nextTheme));
    setToast(nextTheme === 'dark' ? '다크 모드를 켰습니다.' : '라이트 모드로 변경했습니다.');
  }, []);

  const handleSetProfile = useCallback(async (profile: string) => {
    setSettings(await setProfile(profile));
    setToast('직업 프리셋을 선택했습니다.');
  }, []);

  const handleApplyPreset = useCallback(async () => {
    setSettings(await applyPreset());
    setToast('프리셋 후보 규칙을 적용했습니다.');
  }, []);

  const handleRunDiagnostics = useCallback(async () => {
    setSettings(await runDiagnostics());
  }, []);

  const handleExportCsv = useCallback(async () => {
    const result = await exportCsv();
    if (result.message) setToast(result.message);
  }, []);

  const handleExportCsvPeriod = useCallback(async (period: string) => {
    const result = await exportCsvPeriod(period);
    if (result.message) setToast(result.message);
  }, []);

  const handleExportBackup = useCallback(async () => {
    const result = await exportBackup();
    if (result.message) setToast(result.message);
  }, []);

  const handleRestoreBackup = useCallback(async () => {
    const result = await restoreBackup();
    if (result.message) setToast(result.message);
    if (result.dailyGoalMinutes !== undefined) {
      setSettings(result as SettingsData);
      setInbox(null);
      setReview(null);
      setRules(null);
      setReport(null);
      setDashboard(await getDashboard(selectedDayRef.current));
    }
  }, []);

  return {
    handleSaveSettings,
    handleToggleExcludeSelf,
    handleToggleAutoBackup,
    handleToggleStartup,
    handleToggleSettingsNotifications,
    handleSetTheme,
    handleSetProfile,
    handleApplyPreset,
    handleRunDiagnostics,
    handleExportCsv,
    handleExportCsvPeriod,
    handleExportBackup,
    handleRestoreBackup,
  };
}
