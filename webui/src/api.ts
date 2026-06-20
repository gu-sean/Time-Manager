import type { CurrentActivity, DashboardData, InboxData, ReportData, ReviewData, RulesData, SettingsData } from './types';

declare global {
  interface Window {
    pywebview?: {
      api: {
        get_dashboard(): Promise<DashboardData>;
        change_day(delta: number): Promise<DashboardData>;
        return_to_today(): Promise<DashboardData>;
        toggle_notifications(enabled: boolean): Promise<DashboardData>;
        toggle_tracking(): Promise<DashboardData>;
        get_current_activity(): Promise<CurrentActivity | null>;
        send_focus_notification(title: string, body: string): Promise<void>;
        get_inbox(query?: string, category?: string | null): Promise<InboxData>;
        sort_candidates(column: string): Promise<CandidateRow_[]>;
        reclassify_event(eventId: number, category: string): Promise<InboxData>;
        save_event_as_rule(eventId: number, label: string, category: string): Promise<InboxData>;
        delete_event(eventId: number): Promise<InboxData>;
        restore_deleted_event(): Promise<InboxData>;
        classify_candidates(labels: string[], category: string): Promise<InboxData>;
        exclude_candidates(labels: string[]): Promise<InboxData>;
        ignore_candidates(labels: string[]): Promise<InboxData>;
        get_review(): Promise<ReviewData>;
        get_rules(): Promise<RulesData>;
        add_rule(ruleType: string, category: string, value: string): Promise<RulesData>;
        update_rule(oldKey: string, oldValue: string, ruleType: string, category: string, value: string): Promise<RulesData>;
        delete_rule(key: string, value: string): Promise<RulesData>;
        get_report(period?: string): Promise<ReportData>;
        get_settings(): Promise<SettingsData>;
        save_settings(payload: Record<string, unknown>): Promise<SettingsData>;
        toggle_exclude_self(enabled: boolean): Promise<SettingsData>;
        toggle_auto_backup(enabled: boolean): Promise<SettingsData>;
        set_theme(theme: 'light' | 'dark'): Promise<SettingsData>;
        set_profile(profile: string): Promise<SettingsData>;
        apply_preset(): Promise<SettingsData>;
        run_diagnostics(): Promise<SettingsData>;
        export_csv(dayIso?: string | null): Promise<{ message: string }>;
        export_backup(): Promise<{ message: string }>;
        restore_backup(): Promise<{ message: string } & Partial<SettingsData>>;
      };
    };
  }
}

type CandidateRow_ = InboxData['candidates'][number];

let mockDashboard: DashboardData = {
  dateLabel: '오늘',
  viewingToday: true,
  tracking: true,
  stats: [
    { key: 'total', label: '총 사용 시간', value: '6h 15m', delta: '▲ 1h 20m (어제 대비)', badge: { bg: '#EAF1EC', fg: '#6F9A7C', glyph: '⏱' } },
    { key: 'productive', label: '생산적 시간', value: '4h 20m', delta: '▲ 1h 10m (어제 대비)', badge: { bg: '#EAF1EC', fg: '#6F9A7C', glyph: '▲' } },
    { key: 'unproductive', label: '비생산적 시간', value: '1h 15m', delta: '▼ 20m (어제 대비)', badge: { bg: '#F8EDE3', fg: '#CB8056', glyph: '▽' } },
    { key: 'neutral', label: '중립 시간', value: '40m', delta: '▲ 10m (어제 대비)', badge: { bg: '#EBF0F4', fg: '#7E97AC', glyph: '●' } },
    { key: 'score', label: '생산성 점수', value: '82%', delta: '▲ 8점 (어제 대비)', badge: { bg: '#F6EFDD', fg: '#C19A45', glyph: '★' } },
  ],
  donut: {
    total: '6h 15m',
    segments: [
      { category: 'productive', label: '생산적', color: '#7FA98A', pct: 68, time: '4h 20m', ratio: 0.68 },
      { category: 'unproductive', label: '비생산적', color: '#DB9163', pct: 20, time: '1h 15m', ratio: 0.2 },
      { category: 'neutral', label: '중립', color: '#99ABBE', pct: 12, time: '40m', ratio: 0.12 },
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
  focusMode: { enabled: true, streakLabel: '12m', ratio: 0.4, thresholdMinutes: 30 },
  currentActivity: { label: 'App.tsx - time-manager - Visual Studio Code', category: 'productive', categoryLabel: '생산적', color: '#7FA98A' },
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
  candidates: [
    { label: 'Notion', duration: '2h 10m', occurrences: 12 },
    { label: 'Twitter / X', duration: '1h 30m', occurrences: 9 },
    { label: 'Spotify', duration: '3h 00m', occurrences: 18 },
  ],
};

function hasPywebview(): boolean {
  return typeof window !== 'undefined' && !!window.pywebview;
}

export async function getDashboard(): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.get_dashboard();
  return mockDashboard;
}

export async function changeDay(delta: number): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.change_day(delta);
  return mockDashboard;
}

export async function returnToToday(): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.return_to_today();
  return mockDashboard;
}

export async function toggleNotifications(enabled: boolean): Promise<DashboardData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_notifications(enabled);
  mockSettings = { ...mockSettings, notificationsEnabled: enabled };
  mockDashboard = { ...mockDashboard, focusMode: { ...mockDashboard.focusMode, enabled } };
  return mockDashboard;
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

export async function getInbox(query = '', category: string | null = null): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.get_inbox(query, category);
  if (!query && !category) return mockInbox;
  return { ...mockInbox, searchActive: true, resultCount: mockInbox.records.length };
}

export async function sortCandidates(column: string): Promise<CandidateRow_[]> {
  if (hasPywebview()) return window.pywebview!.api.sort_candidates(column);
  const sorted = [...mockInbox.candidates].sort((a, b) =>
    column === 'occurrences' ? b.occurrences - a.occurrences : 0,
  );
  return sorted;
}

export async function reclassifyEvent(eventId: number, category: string): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.reclassify_event(eventId, category);
  mockInbox = {
    ...mockInbox,
    records: mockInbox.records.map((record) => (record.id === eventId ? { ...record, category } : record)),
  };
  return mockInbox;
}

export async function saveEventAsRule(eventId: number, label: string, category: string): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.save_event_as_rule(eventId, label, category);
  return reclassifyEvent(eventId, category);
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

export async function classifyCandidates(labels: string[], category: string): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.classify_candidates(labels, category);
  mockInbox = { ...mockInbox, candidates: mockInbox.candidates.filter((c) => !labels.includes(c.label)) };
  return mockInbox;
}

export async function excludeCandidates(labels: string[]): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.exclude_candidates(labels);
  mockInbox = { ...mockInbox, candidates: mockInbox.candidates.filter((c) => !labels.includes(c.label)) };
  return mockInbox;
}

export async function ignoreCandidates(labels: string[]): Promise<InboxData> {
  if (hasPywebview()) return window.pywebview!.api.ignore_candidates(labels);
  mockInbox = { ...mockInbox, candidates: mockInbox.candidates.filter((c) => !labels.includes(c.label)) };
  return mockInbox;
}

const MOCK_REVIEW: ReviewData = {
  composition: {
    total: '6h 15m',
    segments: [
      { category: 'productive', label: '생산적', color: '#7FA98A', pct: 68, time: '4h 20m' },
      { category: 'unproductive', label: '비생산적', color: '#DB9163', pct: 20, time: '1h 15m' },
      { category: 'neutral', label: '중립', color: '#99ABBE', pct: 12, time: '40m' },
    ],
  },
  highlights: [
    { tag: '생산', tBg: '#EAF1EC', tFg: '#6F9A7C', title: '가장 많이 쓴 생산 활동', value: 'Visual Studio Code', time: '2h 15m', color: '#7FA98A', empty: false },
    { tag: '주의', tBg: '#F8EDE3', tFg: '#CB8056', title: '가장 큰 방해 요소', value: 'YouTube', time: '45m', color: '#DB9163', empty: false },
    { tag: '정리', tBg: '#EBF0F4', tFg: '#7E97AC', title: '정리가 필요한 중립 활동', value: '미분류 4건', time: '', color: '#99ABBE', empty: false },
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

export async function getReview(): Promise<ReviewData> {
  if (hasPywebview()) return window.pywebview!.api.get_review();
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

const MOCK_REPORT: ReportData = {
  period: '최근 7일',
  periodOptions: ['최근 7일', '최근 30일', '이번 달'],
  weeklyScorePct: 82,
  weeklyProgressText: '26h 05m / 30h 00m (82%) · 일간 목표 달성 5일 · 지난주 대비 +45분',
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
  hourly: Array.from({ length: 24 }, (_, hour) => ({
    hour,
    productive: hour >= 8 && hour <= 19 ? 600 : 0,
    unproductive: hour >= 8 && hour <= 19 ? 120 : 0,
    neutral: hour >= 8 && hour <= 19 ? 80 : 0,
  })),
  trend: [62, 70, 66, 78, 74, 82, 80, 88, 84, 90, 86, 82].map((score, i) => ({ day: String(i + 1), score })),
  heatmap: ['월', '화', '수', '목', '금', '토', '일'].map((day, di) => ({
    day,
    cells: Array.from({ length: 24 }, (_, hi) => Math.max(0, Math.sin((hi + 2) / 13 * Math.PI) * (di < 5 ? 1 : 0.4))),
  })),
  daily: [
    { day: '5/20 (월)', total: '6h 15m', prod: '4h 20m', score: 82 },
    { day: '5/19 (일)', total: '3h 40m', prod: '1h 50m', score: 61 },
    { day: '5/18 (토)', total: '2h 55m', prod: '1h 20m', score: 52 },
  ],
  topActivities: [
    { name: 'Visual Studio Code', time: '14h 20m', ratio: 1, color: '#7FA98A' },
    { name: 'Chrome', time: '9h 05m', ratio: 0.64, color: '#7FA98A' },
    { name: 'YouTube', time: '4h 15m', ratio: 0.3, color: '#DB9163' },
  ],
};

export async function getReport(period = '최근 7일'): Promise<ReportData> {
  if (hasPywebview()) return window.pywebview!.api.get_report(period);
  return { ...MOCK_REPORT, period };
}

let mockSettings: SettingsData = {
  dailyGoalMinutes: 180,
  weeklyGoalMinutes: 900,
  unproductiveLimitMinutes: 120,
  workStartHour: 9,
  workEndHour: 18,
  profile: '',
  profileOptions: [
    { value: '', label: '선택 안 함' },
    { value: 'developer', label: '개발자' },
    { value: 'student', label: '학생' },
    { value: 'designer', label: '디자이너' },
  ],
  presetItems: [],
  excludeSelf: true,
  notificationsEnabled: true,
  autoBackupEnabled: false,
  storeDomainOnly: false,
  storeWindowTitles: true,
  retentionDays: 0,
  theme: 'light',
  notificationStatus: 'Windows 알림을 사용할 수 있습니다. 표시되지 않으면 Windows 알림 설정을 확인하세요.',
  diagnosticInfo: '환경: v0.4.0 (dev)\n데이터: (mock)',
  diagnosticResults: '',
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

export async function toggleExcludeSelf(enabled: boolean): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_exclude_self(enabled);
  mockSettings = { ...mockSettings, excludeSelf: enabled };
  return mockSettings;
}

export async function toggleAutoBackup(enabled: boolean): Promise<SettingsData> {
  if (hasPywebview()) return window.pywebview!.api.toggle_auto_backup(enabled);
  mockSettings = { ...mockSettings, autoBackupEnabled: enabled };
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

export async function exportBackup(): Promise<{ message: string }> {
  if (hasPywebview()) return window.pywebview!.api.export_backup();
  return { message: '' };
}

export async function restoreBackup(): Promise<{ message: string } & Partial<SettingsData>> {
  if (hasPywebview()) return window.pywebview!.api.restore_backup();
  return { message: '' };
}

export function waitForApi(): Promise<void> {
  if (!hasPywebview() && typeof window !== 'undefined' && 'pywebview' in window === false) {
  }
  return new Promise((resolve) => {
    if (hasPywebview()) {
      resolve();
      return;
    }
    const onReady = () => {
      window.removeEventListener('pywebviewready', onReady);
      resolve();
    };
    window.addEventListener('pywebviewready', onReady);
    setTimeout(resolve, 300);
  });
}
