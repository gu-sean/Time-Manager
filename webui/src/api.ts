import type { PresetItem, AICoaching, AIModelList, AIRequestPreview, AskResult, CoachingHistoryEntry, AIService, AIRuleSuggestionsResult, AISettingsInput, AITestResult, CurrentActivity, DashboardData, InboxData, InstallUpdateResult, ReportData, ReviewData, RuleSuggestion, RulesData, SettingsData, TrackingOptions, UpdateInfo, RuleReapplyPreview, ActionResult, DeletePreview } from './types';

declare global {
  interface Window {
    pywebview?: {
      api: {
        get_dashboard(dateIso?: string | null): Promise<DashboardData>;
        toggle_notifications(enabled: boolean): Promise<DashboardData>;
        toggle_tracking(): Promise<DashboardData>;
        pause_tracking(minutes: number | null): Promise<DashboardData>;
        set_focus_session(endsAtMs: number | null): Promise<void>;
        preview_delete_target(eventId: number): Promise<DeletePreview>;
        delete_target_records(eventId: number): Promise<ActionResult>;
        add_manual_entry(dateIso: string, start: string, minutes: number | '', label: string, category: string): Promise<ActionResult>;
        preview_delete_period(startIso: string, endIso: string): Promise<DeletePreview>;
        delete_period(startIso: string, endIso: string): Promise<ActionResult>;
        get_current_activity(): Promise<CurrentActivity | null>;
        send_focus_notification(title: string, body: string): Promise<void>;
        get_inbox(query?: string, category?: string | null, dateIso?: string | null): Promise<InboxData>;
        reclassify_event(eventId: number, category: string): Promise<InboxData>;
        add_rule_for_event(eventId: number): Promise<{ message: string; error: string }>;
        delete_event(eventId: number): Promise<InboxData>;
        restore_deleted_event(): Promise<InboxData>;
        get_review(dateIso?: string | null): Promise<ReviewData>;
        get_rules(): Promise<RulesData>;
        preview_rule_reapply(): Promise<RuleReapplyPreview>;
        reapply_rules(): Promise<{ message: string; error: string }>;
        add_rule(ruleType: string, category: string, value: string): Promise<RulesData>;
        update_rule(oldKey: string, oldValue: string, ruleType: string, category: string, value: string): Promise<RulesData>;
        delete_rule(key: string, value: string): Promise<RulesData>;
        get_rule_suggestions(): Promise<RuleSuggestion[]>;
        apply_rule_suggestion(target: string, category: string): Promise<RulesData>;
        get_report(period?: string): Promise<ReportData>;
        get_report_range(startIso: string, endIso: string): Promise<ReportData>;
        get_settings(): Promise<SettingsData>;
        save_settings(payload: Record<string, unknown>): Promise<SettingsData>;
        toggle_auto_backup(enabled: boolean): Promise<SettingsData>;
        toggle_startup(enabled: boolean): Promise<SettingsData>;
        save_tracking_options(changes: TrackingOptions): Promise<SettingsData>;
        set_theme(theme: 'light' | 'dark'): Promise<SettingsData>;
        set_profile(profile: string): Promise<SettingsData>;
        apply_preset(): Promise<SettingsData>;
        create_preset(name: string, emoji: string, source: string): Promise<SettingsData>;
        update_preset(id: string, name: string, emoji: string, items: PresetItem[]): Promise<SettingsData>;
        delete_preset(id: string): Promise<SettingsData>;
        run_diagnostics(): Promise<SettingsData>;
        export_csv(dayIso?: string | null): Promise<{ message: string }>;
        export_csv_period(period: string): Promise<{ message: string }>;
        export_csv_range(startIso: string, endIso: string): Promise<{ message: string }>;
        export_backup(): Promise<{ message: string }>;
        restore_backup(): Promise<{ message: string } & Partial<SettingsData>>;
        check_update(): Promise<UpdateInfo>;
        install_update(assetUrl: string): Promise<InstallUpdateResult>;
        export_logs(): Promise<{ message: string }>;
        save_ai_settings(provider: string, service: string, model: string, baseUrl: string): Promise<SettingsData>;
        set_ai_api_key(service: string, apiKey: string, baseUrl: string): Promise<SettingsData>;
        clear_ai_api_key(service: string, baseUrl: string): Promise<SettingsData>;
        list_ai_models(service: string, baseUrl: string): Promise<AIModelList>;
        test_ai_connection(): Promise<AITestResult>;
        get_ai_rule_suggestions(requestId: string, builtin: boolean): Promise<AIRuleSuggestionsResult>;
        get_ai_coaching(
          scope: string, dateIso: string | null, refresh: boolean, requestId: string, builtin: boolean,
        ): Promise<AICoaching>;
        preview_ai_request(
          kind: string, scope: string, dateIso: string | null, question: string,
        ): Promise<AIRequestPreview>;
        ask_activity(question: string, requestId: string, builtin: boolean): Promise<AskResult>;
        get_coaching_history(): Promise<CoachingHistoryEntry[]>;
        delete_coaching_history(id: number): Promise<CoachingHistoryEntry[]>;
        clear_coaching_history(): Promise<CoachingHistoryEntry[]>;
        add_ai_exclusion(value: string): Promise<SettingsData>;
        remove_ai_exclusion(value: string): Promise<SettingsData>;
        get_dismissed_suggestions(): Promise<string[]>;
        dismiss_rule_suggestion(target: string): Promise<string[]>;
        restore_rule_suggestion(target: string): Promise<string[]>;
        cancel_ai_request(requestId: string): Promise<void>;
      };
    };
  }
}

let mockDashboard: DashboardData = {
  dateLabel: '오늘',
  viewingToday: true,
  tracking: true,
  comparedWith: '어제 같은 시각',
  pausedUntil: '',
  goal: { offDay: false, value: '4시간 20분 / 3시간', pct: 144, ratio: 1, achieved: true, remaining: '' },
  stats: [
    { key: 'total', label: '총 사용 시간', value: '6시간 15분', delta: '▲ 1시간 20분', tone: 'neutral' },
    { key: 'productive', label: '생산적 시간', value: '4시간 20분', delta: '▲ 1시간 10분', tone: 'good' },
    { key: 'unproductive', label: '비생산적 시간', value: '1시간 15분', delta: '▼ 20분', tone: 'good' },
    { key: 'neutral', label: '중립 시간', value: '40분', delta: '▲ 10분', tone: 'neutral' },
    { key: 'score', label: '생산성 점수', value: '82점', delta: '▲ 8점', tone: 'good' },
  ],
  donut: {
    total: '6h 15m',
    segments: [
      { category: 'productive', label: '생산적', color: '#128C6E', pct: 68, time: '4h 20m', ratio: 0.68 },
      { category: 'unproductive', label: '비생산적', color: '#D58528', pct: 20, time: '1h 15m', ratio: 0.2 },
      { category: 'neutral', label: '중립', color: '#7A82D6', pct: 12, time: '40m', ratio: 0.12 },
    ],
  },
  hourly: Array.from({ length: 24 }, (_, hour) => ({
    hour,
    productive: hour >= 8 && hour <= 19 ? 600 + Math.round(Math.sin(hour) * 200) : 0,
    unproductive: hour >= 8 && hour <= 19 ? 120 : 0,
    neutral: hour >= 8 && hour <= 19 ? 80 : 0,
  })),
  topApps: [
    { rank: 1, label: 'Visual Studio Code', time: '2h 15m', category: 'productive', ratio: 1 },
    { rank: 2, label: 'Google Chrome', time: '1h 30m', category: 'neutral', ratio: 0.67 },
    { rank: 3, label: 'ChatGPT', time: '1h 00m', category: 'productive', ratio: 0.44 },
    { rank: 4, label: 'YouTube', time: '45m', category: 'unproductive', ratio: 0.33 },
    { rank: 5, label: 'Discord', time: '20m', category: 'unproductive', ratio: 0.15 },
  ],
  focusSummary: { count: 2, totalTime: '1시간 40분' },
  currentActivity: { label: 'App.tsx - time-manager - Visual Studio Code', category: 'productive', categoryLabel: '생산적', color: '#128C6E' },
};

let mockInbox: InboxData = {
  records: [
    { id: 1, time: '2024-05-20 14:00', category: 'productive', categoryLabel: '생산적', duration: '1h 00m', label: 'main.py · time_manager' },
    { id: 2, time: '2024-05-20 13:00', category: 'productive', categoryLabel: '생산적', duration: '1h 00m', label: 'New chat — 코드 리뷰 요청' },
    { id: 3, time: '2024-05-20 12:00', category: 'unproductive', categoryLabel: '비생산적', duration: '45m', label: '(157) 코딩 음악 — YouTube' },
    { id: 4, time: '2024-05-20 11:15', category: 'neutral', categoryLabel: '중립', duration: '45m', label: 'news.ycombinator.com' },
  ],
  searchActive: false,
  resultCount: null,
  query: '',
  category: null,
};

/** 백엔드 없는 개발 서버(예시 데이터 표시)에서만 false. */
function hasPywebview(): boolean {
  // 빌드된 앱은 가짜 데이터를 보여주면 안 됨 → 항상 백엔드 호출 (또는 실패)
  return !import.meta.env.DEV || !!window.pywebview?.api;
}

export async function getDashboard(dateIso?: string): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.get_dashboard(dateIso ?? null);
  return mockDashboard;
}

export async function toggleNotifications(enabled: boolean): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_notifications(enabled);
  mockSettings = { ...mockSettings, notificationsEnabled: enabled };
  return mockDashboard;
}

export async function pauseTracking(minutes: number | null): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.pause_tracking(minutes);
  mockDashboard = { ...mockDashboard, tracking: false, pausedUntil: minutes ? '15:30' : '' };
  return mockDashboard;
}

/** 집중 타이머의 집중 단계가 끝나는 때 (epoch ms). 멈추거나 쉬면 null. */
export async function setFocusSession(endsAtMs: number | null): Promise<void> {
  if (hasPywebview()) await window.pywebview!.api.set_focus_session(endsAtMs);
}

export async function previewDeleteTarget(eventId: number): Promise<DeletePreview> {
  if (hasPywebview()) return window.pywebview!.api.preview_delete_target(eventId);
  return { error: '', target: 'youtube.com', kindLabel: '사이트', count: 12, timeLabel: '3시간 10분' };
}

export async function deleteTargetRecords(eventId: number): Promise<ActionResult> {
  if (hasPywebview()) return window.pywebview!.api.delete_target_records(eventId);
  return { message: 'youtube.com 사이트의 기록 12건을 완전히 지웠어요.', error: '' };
}

export async function addManualEntry(
  dateIso: string, start: string, minutes: number | '', label: string, category: string,
): Promise<ActionResult> {
  if (hasPywebview()) return window.pywebview!.api.add_manual_entry(dateIso, start, minutes, label, category);
  return { message: `${start}부터 ${minutes}분을 추가했어요.`, error: '' };
}

export async function previewDeletePeriod(startIso: string, endIso: string): Promise<DeletePreview> {
  if (hasPywebview()) return window.pywebview!.api.preview_delete_period(startIso, endIso);
  return { error: '', count: 40, timeLabel: '6시간 4분' };
}

export async function deletePeriod(startIso: string, endIso: string): Promise<ActionResult> {
  if (hasPywebview()) return window.pywebview!.api.delete_period(startIso, endIso);
  return { message: `${startIso}~${endIso} 기록 40건을 완전히 지웠어요.`, error: '' };
}

export async function toggleTracking(): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_tracking();
  mockDashboard = { ...mockDashboard, tracking: !mockDashboard.tracking };
  return mockDashboard;
}

export async function getCurrentActivity(): Promise<CurrentActivity | null> {
  if (hasPywebview()) return window.pywebview!.api.get_current_activity();
  return mockDashboard.currentActivity;
}

export async function sendFocusNotification(title: string, body: string): Promise<void> {
  if (hasPywebview()) {
    await window.pywebview!.api.send_focus_notification(title, body);
  }
}

export async function getInbox(query = '', category: string | null = null, dateIso?: string): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.get_inbox(query, category, dateIso ?? null);
  if (!query && !category) return mockInbox;
  const records = mockInbox.records.filter((record) => !category || record.category === category);
  return { ...mockInbox, records, searchActive: true, resultCount: records.length, query, category };
}

export async function reclassifyEvent(eventId: number, category: string): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.reclassify_event(eventId, category);
  mockInbox = {
    ...mockInbox,
    records: mockInbox.records.map((record) =>
      record.id === eventId
        ? { ...record, category, categoryLabel: { productive: '생산적', unproductive: '비생산적' }[category] ?? '중립' }
        : record,
    ),
  };
  return mockInbox;
}

export async function addRuleForEvent(eventId: number): Promise<{ message: string; error: string }> {
  if (hasPywebview()) return window.pywebview!.api.add_rule_for_event(eventId);
  return { message: '규칙을 추가했어요. (예시)', error: '' };
}

export async function deleteEvent(eventId: number): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.delete_event(eventId);
  mockInbox = { ...mockInbox, records: mockInbox.records.filter((record) => record.id !== eventId) };
  return mockInbox;
}

export async function restoreDeletedEvent(): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.restore_deleted_event();
  return mockInbox;
}

const MOCK_REVIEW: ReviewData = {
  composition: {
    total: '6h 15m',
    segments: [
      { category: 'productive', label: '생산적', color: '#128C6E', pct: 68, time: '4h 20m' },
      { category: 'unproductive', label: '비생산적', color: '#D58528', pct: 20, time: '1h 15m' },
      { category: 'neutral', label: '중립', color: '#7A82D6', pct: 12, time: '40m' },
    ],
  },
  highlights: [
    { tag: '생산', tBg: '#EAF1EC', tFg: '#6F9A7C', title: '가장 많이 쓴 생산 활동', value: 'Visual Studio Code', time: '2h 15m', color: '#128C6E', empty: false },
    { tag: '주의', tBg: '#F8EDE3', tFg: '#CB8056', title: '가장 큰 방해 요소', value: 'YouTube', time: '45m', color: '#D58528', empty: false },
    { tag: '정리', tBg: '#EBF0F4', tFg: '#7E97AC', title: '정리가 필요한 중립 활동', value: '미분류 4건', time: '', color: '#7A82D6', empty: false },
  ],
  suggestion: '오후 집중 패턴 — 14~16시 생산성이 가장 높아요. 이 시간대의 활동 패턴을 유지해보세요.',
  flow: {
    empty: false,
    note: '',
    stats: [
      { label: '활동 흐름', value: '12', unit: '개' },
      { label: '대상 전환', value: '8', unit: '회' },
      { label: '분류 전환', value: '5', unit: '회' },
      { label: '최장 생산 구간', value: '32m', unit: '' },
    ],
  },
  focus: {
    empty: false,
    note: '가장 깊은 몰입 · Visual Studio Code',
    stats: [
      { label: '집중 구간', value: '2', unit: '개' },
      { label: '누적 시간', value: '1h 40m', unit: '' },
      { label: '최장 몰입', value: '55m', unit: '' },
    ],
  },
};

export async function getReview(dateIso?: string): Promise<ReviewData> {
  if (hasPywebview()) return window.pywebview!.api.get_review(dateIso ?? null);
  return MOCK_REVIEW;
}

const RULE_KEY_LABELS: Record<string, [string, string]> = {
  productive_domains: ['생산적', '도메인'],
  productive_title_keywords: ['생산적', '창 제목 키워드'],
  productive_apps: ['생산적', '앱 이름'],
  unproductive_domains: ['비생산적', '도메인'],
  unproductive_title_keywords: ['비생산적', '창 제목 키워드'],
  unproductive_apps: ['비생산적', '앱 이름'],
  neutral_title_keywords: ['중립', '창 제목 키워드'],
  excluded_apps: ['기록 제외', '앱 이름'],
};

function mockRuleKey(ruleType: string, category: string): string {
  if (category === '중립') return 'neutral_title_keywords';
  if (category === '기록 제외') return 'excluded_apps';
  const prefix = category === '생산적' ? 'productive' : 'unproductive';
  if (ruleType === '도메인') return `${prefix}_domains`;
  if (ruleType === '창 제목 키워드') return `${prefix}_title_keywords`;
  return `${prefix}_apps`;
}

function renumber(items: RulesData['items']): RulesData {
  const renumbered = items.map((item, index) => ({ ...item, priority: index + 1 }));
  return { items: renumbered, total: renumbered.length };
}

let mockRules: RulesData = renumber([
  { priority: 1, category: '생산적', ruleType: '도메인', key: 'productive_domains', value: 'github.com' },
  { priority: 2, category: '생산적', ruleType: '앱 이름', key: 'productive_apps', value: 'Visual Studio Code' },
  { priority: 3, category: '비생산적', ruleType: '도메인', key: 'unproductive_domains', value: 'youtube.com' },
]);

export async function getRules(): Promise<RulesData> {
  if (hasPywebview()) return window.pywebview!.api.get_rules();
  return mockRules;
}

export async function addRule(ruleType: string, category: string, value: string): Promise<RulesData> {
  if (hasPywebview()) return window.pywebview!.api.add_rule(ruleType, category, value);
  const key = mockRuleKey(ruleType, category);
  const [cat, type] = RULE_KEY_LABELS[key];
  mockRules = renumber([...mockRules.items, { priority: 0, category: cat, ruleType: type, key, value }]);
  return mockRules;
}

export async function updateRule(
  oldKey: string,
  oldValue: string,
  ruleType: string,
  category: string,
  value: string,
): Promise<RulesData> {
  if (hasPywebview()) return window.pywebview!.api.update_rule(oldKey, oldValue, ruleType, category, value);
  const key = mockRuleKey(ruleType, category);
  const [cat, type] = RULE_KEY_LABELS[key];
  mockRules = renumber(
    mockRules.items.map((item) =>
      item.key === oldKey && item.value === oldValue
        ? { ...item, key, category: cat, ruleType: type, value }
        : item,
    ),
  );
  return mockRules;
}

export async function deleteRule(key: string, value: string): Promise<RulesData> {
  if (hasPywebview()) return window.pywebview!.api.delete_rule(key, value);
  mockRules = renumber(mockRules.items.filter((r) => !(r.key === key && r.value === value)));
  return mockRules;
}

let mockSuggestions: RuleSuggestion[] = [
  { target: 'notion.so', timeLabel: '42분', displayTarget: 'notion.so' },
  { target: 'Slack', timeLabel: '18분', displayTarget: 'Slack' },
];

export async function getRuleSuggestions(): Promise<RuleSuggestion[]> {
  if (hasPywebview()) return window.pywebview!.api.get_rule_suggestions();
  return mockSuggestions;
}

export async function applyRuleSuggestion(target: string, category: string): Promise<RulesData> {
  if (hasPywebview()) return window.pywebview!.api.apply_rule_suggestion(target, category);
  mockSuggestions = mockSuggestions.filter((s) => s.target !== target);
  return mockRules;
}

const MOCK_REPORT: ReportData = {
  period: '최근 7일',
  periodOptions: ['최근 7일', '최근 30일', '이번 달'],
  startIso: new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10),
  endIso: new Date().toISOString().slice(0, 10),
  weeklyScorePct: 82,
  weeklyProgressText: '26h 05m / 30h 00m (82%) · 일간 목표 달성 5일 · 지난주 같은 시점보다 45분 증가',
  coachingText: '반복 비생산 활동은 YouTube입니다. 21시 전후의 사용 패턴을 먼저 점검해보세요.',
  weekdayText: '금요일의 생산 흐름이 가장 안정적입니다.',
  weekdayBars: [
    { day: '월', seconds: 14760, pct: 82, isWeekend: false },
    { day: '화', seconds: 13680, pct: 76, isWeekend: false },
    { day: '수', seconds: 15840, pct: 88, isWeekend: false },
    { day: '목', seconds: 12780, pct: 71, isWeekend: false },
    { day: '금', seconds: 16200, pct: 90, isWeekend: false },
    { day: '토', seconds: 7920, pct: 44, isWeekend: true },
    { day: '일', seconds: 6840, pct: 38, isWeekend: true },
  ],
  insightMain: '평균 생산 점수는 76%입니다. 가장 약한 날이 5/18(52%)이고, 비생산 피크는 21시입니다.',
  insightSub: '이번 주는 금요일 오후에 생산성이 가장 높았어요.',
  trend: [62, 70, 66, 78, 74, 82, 80, 88, 84, 90, 86, 82].map((score, i) => ({ date: `2026-05-${String(i + 9).padStart(2, '0')}`, score })),
  heatmap: ['월', '화', '수', '목', '금', '토', '일'].map((day, di) => ({
    day,
    cells: Array.from({ length: 24 }, (_, hi) => Math.max(0, Math.sin((hi + 2) / 13 * Math.PI) * (di < 5 ? 1 : 0.4))),
    seconds: Array.from({ length: 24 }, (_, hi) => Math.round(Math.max(0, Math.sin((hi + 2) / 13 * Math.PI) * (di < 5 ? 1 : 0.4)) * 3600)),
  })),
  daily: [
    { day: '5/20 (월)', total: '6h 15m', prod: '4h 20m', score: 82 },
    { day: '5/19 (일)', total: '3h 40m', prod: '1h 50m', score: 61 },
    { day: '5/18 (토)', total: '2h 55m', prod: '1h 20m', score: 52 },
  ],
  topActivities: [
    { name: 'Visual Studio Code', time: '14h 20m', ratio: 1, color: '#128C6E' },
    { name: 'Chrome', time: '9h 05m', ratio: 0.64, color: '#128C6E' },
    { name: 'YouTube', time: '4h 15m', ratio: 0.3, color: '#D58528' },
  ],
};

export async function getReport(period = '최근 7일'): Promise<ReportData> {
  if (hasPywebview()) return window.pywebview!.api.get_report(period);
  return { ...MOCK_REPORT, period };
}

export async function getReportRange(startIso: string, endIso: string): Promise<ReportData> {
  if (hasPywebview()) return window.pywebview!.api.get_report_range(startIso, endIso);
  return { ...MOCK_REPORT, period: `${startIso}–${endIso}` };
}

function mockService(value: string, label: string, overrides: Partial<AIService>): AIService {
  return {
    value, label, help: '', editableUrl: false, keyRequired: false, keyPlaceholder: '',
    suggestedModels: [], model: '', baseUrl: '', hasKey: false, ...overrides,
  };
}

function updateMockService(service: string, changes: Partial<AIService>): void {
  mockSettings = {
    ...mockSettings,
    aiServices: mockSettings.aiServices.map((s) => (s.value === service ? { ...s, ...changes } : s)),
  };
}

let mockSettings: SettingsData = {
  appVersion: '1.3.0',
  dailyGoalMinutes: 180,
  weeklyGoalMinutes: 900,
  unproductiveLimitMinutes: 120,
  workStartHour: 9,
  workEndHour: 18,
  profile: '',
  profileOptions: [
    { value: '', label: '선택 안 함', emoji: '', custom: false },
    { value: 'developer', label: '개발자', emoji: '💻', custom: false },
    { value: 'student', label: '학생', emoji: '📚', custom: false },
    { value: 'designer', label: '디자이너', emoji: '🎨', custom: false },
  ],
  presetItems: [],
  notificationsEnabled: true,
  autoBackupEnabled: true,
  startupEnabled: false,
  idleMinutes: 5,
  recordMedia: true,
  trimIdleTime: false,
  closeToTray: true,
  focusAlert: true,
  goalWeekdays: [0, 1, 2, 3, 4, 5, 6],
  storeDomainOnly: true,
  storeWindowTitles: true,
  retentionDays: 0,
  theme: 'light',
  notificationStatus: 'Windows 알림을 사용할 수 있습니다. 표시되지 않으면 Windows 알림 설정을 확인하세요.',
  diagnosticInfo: '환경: v0.4.0 (dev)\n데이터: (mock)',
  diagnosticResults: '',
  aiProvider: 'local',
  aiProviderOptions: [
    { value: 'local', label: '내장 분석 (무료 · PC에서만 처리)' },
    { value: 'model', label: '개인 모델 (Claude · GPT · Ollama 등)' },
  ],
  aiService: 'claude',
  aiExcludedTargets: [],
  aiServices: [
    mockService('claude', 'Claude (Anthropic)', { keyRequired: true, model: 'claude-opus-5-5', baseUrl: 'https://api.anthropic.com' }),
    mockService('openai', 'GPT (OpenAI)', { keyRequired: true, baseUrl: 'https://api.openai.com/v1' }),
    mockService('ollama', 'Ollama', { editableUrl: true, baseUrl: 'http://localhost:11434/v1' }),
  ],
};

export async function getSettings(): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.get_settings();
  return mockSettings;
}

export async function saveSettings(payload: Record<string, unknown>): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.save_settings(payload);
  mockSettings = { ...mockSettings, ...payload };
  return mockSettings;
}

export async function toggleAutoBackup(enabled: boolean): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_auto_backup(enabled);
  mockSettings = { ...mockSettings, autoBackupEnabled: enabled };
  return mockSettings;
}

export async function toggleStartup(enabled: boolean): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_startup(enabled);
  mockSettings = { ...mockSettings, startupEnabled: enabled };
  return mockSettings;
}

export async function previewRuleReapply(): Promise<RuleReapplyPreview> {
  if (hasPywebview()) return window.pywebview!.api.preview_rule_reapply();
  return {
    count: 12,
    timeLabel: '1시간 5분',
    items: [{ target: 'notion.so', from: '중립', to: '생산적', count: 12, timeLabel: '1시간 5분' }],
    more: 0,
  };
}

export async function reapplyRules(): Promise<{ message: string; error: string }> {
  if (hasPywebview()) return window.pywebview!.api.reapply_rules();
  return { message: '지난 기록 12건의 분류를 바꿨어요.', error: '' };
}

export async function saveTrackingOptions(changes: TrackingOptions): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.save_tracking_options(changes);
  const { idleMinutes, ...toggles } = changes;
  mockSettings = { ...mockSettings, ...toggles, ...(typeof idleMinutes === 'number' ? { idleMinutes } : {}) };
  return mockSettings;
}

export async function setTheme(theme: 'light' | 'dark'): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.set_theme(theme);
  mockSettings = { ...mockSettings, theme };
  return mockSettings;
}

export async function setProfile(profile: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.set_profile(profile);
  mockSettings = { ...mockSettings, profile };
  return mockSettings;
}

export async function applyPreset(): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.apply_preset();
  return mockSettings;
}

export async function runDiagnostics(): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.run_diagnostics();
  return { ...mockSettings, diagnosticResults: '[OK] 모든 항목이 정상입니다.' };
}

export async function exportCsv(): Promise<{ message: string }> {
  if (hasPywebview()) return window.pywebview!.api.export_csv();
  return { message: '' };
}

export async function exportCsvPeriod(period: string): Promise<{ message: string }> {
  if (hasPywebview()) return window.pywebview!.api.export_csv_period(period);
  return { message: `${period} CSV 내보내기 (mock)` };
}

export async function exportCsvRange(startIso: string, endIso: string): Promise<{ message: string }> {
  if (hasPywebview()) return window.pywebview!.api.export_csv_range(startIso, endIso);
  return { message: `${startIso}–${endIso} CSV 내보내기 (mock)` };
}

export async function exportBackup(): Promise<{ message: string }> {
  if (hasPywebview()) return window.pywebview!.api.export_backup();
  return { message: '' };
}

export async function restoreBackup(): Promise<{ message: string } & Partial<SettingsData>> {
  if (hasPywebview()) return window.pywebview!.api.restore_backup();
  return { message: '' };
}

export async function checkUpdate(): Promise<UpdateInfo> {
  if (hasPywebview()) return window.pywebview!.api.check_update();
  return { hasUpdate: false, latest: '', current: '', url: '', assetUrl: '', error: '' };
}

export async function installUpdate(assetUrl: string): Promise<InstallUpdateResult> {
  if (hasPywebview()) return window.pywebview!.api.install_update(assetUrl);
  return { started: false, error: '' };
}

export async function exportLogs(): Promise<{ message: string }> {
  if (hasPywebview()) return window.pywebview!.api.export_logs();
  return { message: '' };
}

const DEV_FALLBACK_MS = 2000;
const API_TIMEOUT_MS = 15000;

/** 앱 백엔드를 호출할 수 있게 되면 완료. */
export function waitForApi(): Promise<void> {
  const ready = () => typeof window.pywebview?.api?.get_dashboard === 'function';
  return new Promise((resolve, reject) => {
    if (ready()) {
      resolve();
      return;
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      const waited = Date.now() - started;
      // 백엔드 없이 진행(예시 데이터)할 수 있는 것은 브라우저 개발 서버뿐
      if (ready() || (import.meta.env.DEV && waited > DEV_FALLBACK_MS)) {
        window.clearInterval(timer);
        resolve();
      } else if (waited > API_TIMEOUT_MS) {
        window.clearInterval(timer);
        reject(new Error('the app backend did not become ready'));
      }
    }, 50);
  });
}

export async function saveAiSettings(input: AISettingsInput): Promise<SettingsData> {
  if (hasPywebview()) {
    return window.pywebview!.api.save_ai_settings(input.provider, input.service, input.model, input.baseUrl);
  }
  mockSettings = { ...mockSettings, aiProvider: input.provider };
  if (input.provider === 'model') {
    mockSettings = { ...mockSettings, aiService: input.service };
    updateMockService(input.service, { model: input.model, baseUrl: input.baseUrl });
  }
  return mockSettings;
}

export async function setAiApiKey(service: string, apiKey: string, baseUrl: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.set_ai_api_key(service, apiKey, baseUrl);
  updateMockService(service, { hasKey: apiKey.trim().length > 0 });
  return mockSettings;
}

export async function clearAiApiKey(service: string, baseUrl: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.clear_ai_api_key(service, baseUrl);
  updateMockService(service, { hasKey: false });
  return mockSettings;
}

export async function listAiModels(service: string, baseUrl: string): Promise<AIModelList> {
  if (hasPywebview()) return window.pywebview!.api.list_ai_models(service, baseUrl);
  return { models: ['example-model-small', 'example-model-large'], error: '' };
}

export async function testAiConnection(): Promise<AITestResult> {
  if (hasPywebview()) return window.pywebview!.api.test_ai_connection();
  return { ok: true, message: '연결에 성공했습니다.' };
}

export async function previewAiRequest(
  kind: 'suggestions' | 'coaching' | 'question',
  scope: 'day' | 'week' = 'day',
  dateIso: string | null = null,
  question = '',
): Promise<AIRequestPreview> {
  if (hasPywebview()) return window.pywebview!.api.preview_ai_request(kind, scope, dateIso, question);
  return {
    serviceLabel: 'Ollama', url: 'http://localhost:11434/v1/chat/completions', model: 'example-model',
    instructions: '(예시 지침)', data: JSON.stringify({ targets: ['notion.exe', 'reddit.com'] }, null, 2), error: '',
  };
}

export async function askActivity(question: string, requestId: string, builtin: boolean): Promise<AskResult> {
  if (hasPywebview()) return window.pywebview!.api.ask_activity(question, requestId, builtin);
  return {
    answer: '사용 시간은 모두 1시간 20분이에요.', interpretation: '기간 (예시) · 분류 전체 · 대상 전체',
    rows: [], note: '', source: '내장 분석', error: '', canFallback: false,
  };
}

let mockHistory: CoachingHistoryEntry[] = [];

export async function getCoachingHistory(): Promise<CoachingHistoryEntry[]> {
  if (hasPywebview()) return window.pywebview!.api.get_coaching_history();
  return mockHistory;
}

export async function deleteCoachingHistory(id: number): Promise<CoachingHistoryEntry[]> {
  if (hasPywebview()) return window.pywebview!.api.delete_coaching_history(id);
  mockHistory = mockHistory.filter((entry) => entry.id !== id);
  return mockHistory;
}

export async function clearCoachingHistory(): Promise<CoachingHistoryEntry[]> {
  if (hasPywebview()) return window.pywebview!.api.clear_coaching_history();
  mockHistory = [];
  return mockHistory;
}

export async function addAiExclusion(value: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.add_ai_exclusion(value);
  mockSettings = { ...mockSettings, aiExcludedTargets: [...new Set([...mockSettings.aiExcludedTargets, value.trim()])] };
  return mockSettings;
}

export async function removeAiExclusion(value: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.remove_ai_exclusion(value);
  mockSettings = { ...mockSettings, aiExcludedTargets: mockSettings.aiExcludedTargets.filter((v) => v !== value) };
  return mockSettings;
}

let mockDismissed: string[] = [];

export async function getDismissedSuggestions(): Promise<string[]> {
  if (hasPywebview()) return window.pywebview!.api.get_dismissed_suggestions();
  return mockDismissed;
}

export async function dismissRuleSuggestion(target: string): Promise<string[]> {
  if (hasPywebview()) return window.pywebview!.api.dismiss_rule_suggestion(target);
  mockDismissed = [...new Set([...mockDismissed, target.toLowerCase()])];
  return mockDismissed;
}

export async function restoreRuleSuggestion(target: string): Promise<string[]> {
  if (hasPywebview()) return window.pywebview!.api.restore_rule_suggestion(target);
  mockDismissed = mockDismissed.filter((name) => name !== target);
  return mockDismissed;
}

export async function createPreset(name: string, emoji: string, source: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.create_preset(name, emoji, source);
  const value = `custom:${Date.now()}`;
  mockSettings = {
    ...mockSettings,
    profile: value,
    presetItems: [],
    profileOptions: [...mockSettings.profileOptions, { value, label: name, emoji: emoji || '🧩', custom: true }],
  };
  return mockSettings;
}

export async function updatePreset(id: string, name: string, emoji: string, items: PresetItem[]): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.update_preset(id, name, emoji, items);
  mockSettings = {
    ...mockSettings,
    presetItems: items,
    profileOptions: mockSettings.profileOptions.map((o) => (o.value === id ? { ...o, label: name, emoji } : o)),
  };
  return mockSettings;
}

export async function deletePreset(id: string): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.delete_preset(id);
  mockSettings = {
    ...mockSettings,
    profile: '',
    presetItems: [],
    profileOptions: mockSettings.profileOptions.filter((o) => o.value !== id),
  };
  return mockSettings;
}

export async function cancelAiRequest(requestId: string): Promise<void> {
  if (hasPywebview()) await window.pywebview!.api.cancel_ai_request(requestId);
}

export async function getAiRuleSuggestions(requestId: string, builtin: boolean): Promise<AIRuleSuggestionsResult> {
  if (hasPywebview()) return window.pywebview!.api.get_ai_rule_suggestions(requestId, builtin);
  return {
    items: [
      { target: 'notion.exe', displayTarget: 'notion.exe', timeLabel: '1시간 20분', category: 'productive', categoryLabel: '생산적', reason: '문서·업무 정리 도구' },
      { target: 'reddit.com', displayTarget: 'reddit.com', timeLabel: '35분', category: 'unproductive', categoryLabel: '비생산적', reason: '소셜 피드 사이트' },
    ],
    skipped: 1,
    excluded: 0,
    source: '내장 분석',
    error: '',
    canFallback: false,
  };
}

export async function getAiCoaching(
  scope: 'day' | 'week',
  dateIso: string | null,
  refresh: boolean,
  requestId: string,
  builtin: boolean,
): Promise<AICoaching> {
  if (hasPywebview()) return window.pywebview!.api.get_ai_coaching(scope, dateIso, refresh, requestId, builtin);
  return {
    headline: '오후 집중이 가장 좋았어요',
    insights: ['14~16시 생산 시간이 가장 길었어요.', 'YouTube가 하루 45분으로 가장 큰 방해 요소였어요.'],
    actions: ['오후 집중 시간대에 알림을 꺼 보세요.'],
    scopeLabel: scope === 'week' ? '최근 7일' : '오늘',
    source: '내장 분석',
    generated: false,
    canFallback: false,
    error: '',
  };
}
