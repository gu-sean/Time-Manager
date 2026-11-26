import { useCallback } from 'react';
import type { RefObject } from 'react';
import {
  createPreset,
  deletePreset,
  updatePreset,
  addAiExclusion,
  removeAiExclusion,
  applyPreset,
  clearAiApiKey,
  checkUpdate,
  exportBackup,
  exportCsv,
  exportCsvPeriod,
  exportLogs,
  getDashboard,
  getSettings,
  installUpdate,
  listAiModels,
  restoreBackup,
  runDiagnostics,
  saveAiSettings,
  saveSettings,
  setAiApiKey,
  setProfile,
  setTheme,
  testAiConnection,
  toggleAutoBackup,
  toggleNotifications,
  toggleStartup,
  saveTrackingOptions,
} from '../api';
import type { PresetItem, AIModelList, AISettingsInput, AITestResult, DashboardData, InboxData, InstallUpdateResult, ReportData, ReviewData, RulesData, SettingsData, TrackingOptions, UpdateInfo } from '../types';

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
  }, [setSettings, setToast]);

  const handleToggleAutoBackup = useCallback(async (enabled: boolean) => {
    setSettings(await toggleAutoBackup(enabled));
    setToast(enabled ? '자동 백업을 켰습니다.' : '자동 백업을 껐습니다.');
  }, [setSettings, setToast]);

  const handleToggleStartup = useCallback(async (enabled: boolean) => {
    const result = await toggleStartup(enabled);
    setSettings(result);
    setToast(result.error ? '' : enabled ? '시작 시 자동 실행을 켰습니다.' : '시작 시 자동 실행을 껐습니다.');
  }, [setSettings, setToast]);

  const handleSaveTracking = useCallback(async (changes: TrackingOptions) => {
    const result = await saveTrackingOptions(changes);
    setSettings(result);
    setToast(result.error ? '' : '기록 방식을 저장했습니다.');
  }, [setSettings, setToast]);

  const handleToggleSettingsNotifications = useCallback(async (enabled: boolean) => {
    setDashboard(await toggleNotifications(enabled));
    setSettings(await getSettings());
    setToast(enabled ? '목표·집중 알림을 켰습니다.' : '목표·집중 알림을 껐습니다.');
  }, [setDashboard, setSettings, setToast]);

  const handleSetTheme = useCallback(async (nextTheme: 'light' | 'dark') => {
    setSettings(await setTheme(nextTheme));
    setToast(nextTheme === 'dark' ? '다크 모드를 켰습니다.' : '라이트 모드로 변경했습니다.');
  }, [setSettings, setToast]);

  const handleSetProfile = useCallback(async (profile: string) => {
    setSettings(await setProfile(profile));
    setToast('직업 프리셋을 선택했습니다.');
  }, [setSettings, setToast]);

  const handleApplyPreset = useCallback(async () => {
    const result = await applyPreset();
    setSettings(result);
    setToast(result.error ? '' : result.notice ?? '프리셋 후보 규칙을 적용했습니다.');
    setRules(null); // 규칙 화면은 새 규칙으로 다시 로드
  }, [setRules, setSettings, setToast]);

  const handleCreatePreset = useCallback(async (name: string, emoji: string, source: string) => {
    const result = await createPreset(name, emoji, source);
    // 폼에서 오류를 표시하므로 화면 아래에 반복하지 않음
    if (!result.error) {
      setSettings(result);
      setToast('프리셋을 만들었습니다.');
    }
    return result;
  }, [setSettings, setToast]);

  const handleUpdatePreset = useCallback(async (id: string, name: string, emoji: string, items: PresetItem[]) => {
    const result = await updatePreset(id, name, emoji, items);
    if (!result.error) {
      setSettings(result);
      setToast('프리셋을 저장했습니다. 규칙에 반영하려면 적용을 눌러주세요.');
    }
    return result;
  }, [setSettings, setToast]);

  const handleDeletePreset = useCallback(async (id: string) => {
    setSettings(await deletePreset(id));
    setToast('프리셋을 삭제했습니다.');
  }, [setSettings, setToast]);

  const handleRunDiagnostics = useCallback(async () => {
    setSettings(await runDiagnostics());
  }, [setSettings]);

  const handleCheckUpdate = useCallback(async (): Promise<UpdateInfo> => {
    return checkUpdate();
  }, []);

  const handleInstallUpdate = useCallback(async (assetUrl: string): Promise<InstallUpdateResult> => {
    return installUpdate(assetUrl);
  }, []);

  const handleExportLogs = useCallback(async () => {
    const result = await exportLogs();
    if (result.message) setToast(result.message);
  }, [setToast]);

  const handleExportCsv = useCallback(async () => {
    const result = await exportCsv();
    if (result.message) setToast(result.message);
  }, [setToast]);

  const handleExportCsvPeriod = useCallback(async (period: string) => {
    const result = await exportCsvPeriod(period);
    if (result.message) setToast(result.message);
  }, [setToast]);

  const handleExportBackup = useCallback(async () => {
    const result = await exportBackup();
    if (result.message) setToast(result.message);
  }, [setToast]);

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
  }, [selectedDayRef, setDashboard, setInbox, setReport, setReview, setRules, setSettings, setToast]);

  const handleSaveAiSettings = useCallback(async (input: AISettingsInput) => {
    const result = await saveAiSettings(input);
    setSettings(result);
    if (!result.error) setToast('분석 방식을 저장했습니다.');
  }, [setSettings, setToast]);

  const handleSetAiApiKey = useCallback(async (service: string, apiKey: string, baseUrl: string) => {
    const result = await setAiApiKey(service, apiKey, baseUrl);
    setSettings(result);
    if (!result.error) setToast('API 키를 안전하게 저장했습니다.');
  }, [setSettings, setToast]);

  const handleClearAiApiKey = useCallback(async (service: string, baseUrl: string) => {
    setSettings(await clearAiApiKey(service, baseUrl));
    setToast('API 키를 삭제했습니다.');
  }, [setSettings, setToast]);

  const handleListAiModels = useCallback(async (service: string, baseUrl: string): Promise<AIModelList> => {
    return listAiModels(service, baseUrl);
  }, []);

  const handleAddAiExclusion = useCallback(async (value: string) => {
    const result = await addAiExclusion(value);
    setSettings(result);
    if (!result.error) setToast('전송 제외 목록에 추가했습니다.');
  }, [setSettings, setToast]);

  const handleRemoveAiExclusion = useCallback(async (value: string) => {
    setSettings(await removeAiExclusion(value));
    setToast(`'${value}'을(를) 전송 제외 목록에서 뺐습니다.`);
  }, [setSettings, setToast]);

  const handleTestAiConnection = useCallback(async (): Promise<AITestResult> => {
    return testAiConnection();
  }, []);

  return {
    handleSaveAiSettings,
    handleSetAiApiKey,
    handleClearAiApiKey,
    handleTestAiConnection,
    handleListAiModels,
    handleAddAiExclusion,
    handleRemoveAiExclusion,
    handleSaveSettings,
    handleToggleAutoBackup,
    handleToggleStartup,
    handleSaveTracking,
    handleToggleSettingsNotifications,
    handleSetTheme,
    handleSetProfile,
    handleApplyPreset,
    handleCreatePreset,
    handleUpdatePreset,
    handleDeletePreset,
    handleRunDiagnostics,
    handleCheckUpdate,
    handleInstallUpdate,
    handleExportLogs,
    handleExportCsv,
    handleExportCsvPeriod,
    handleExportBackup,
    handleRestoreBackup,
  };
}
