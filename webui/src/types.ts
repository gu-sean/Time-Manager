export interface StatBadge {
  bg: string;
  fg: string;
  glyph: string;
}

export interface StatCard {
  key: string;
  label: string;
  value: string;
  delta: string;
  badge: StatBadge;
}

export interface DonutSegment {
  category: string;
  label: string;
  color: string;
  pct: number;
  time: string;
  ratio: number;
}

export interface HourlyRow {
  hour: number;
  productive: number;
  unproductive: number;
  neutral: number;
}

export interface TopAppRow {
  rank: number;
  label: string;
  time: string;
  category: string;
  ratio: number;
}

export interface FocusMode {
  enabled: boolean;
  streakLabel: string;
  ratio: number;
  thresholdMinutes: number;
}

export interface FocusSummary {
  count: number;
  totalTime: string | null;
}

export interface CurrentActivity {
  label: string;
  category: string;
  categoryLabel: string;
  color: string;
}

export interface DashboardData {
  dateLabel: string;
  viewingToday: boolean;
  tracking: boolean;
  stats: StatCard[];
  donut: { total: string; segments: DonutSegment[] };
  hourly: HourlyRow[];
  topApps: TopAppRow[];
  focusMode: FocusMode;
  focusSummary: FocusSummary;
  currentActivity: CurrentActivity | null;
}

export interface InboxRecord {
  id: number;
  time: string;
  category: string;
  categoryLabel: string;
  duration: string;
  label: string;
}

export interface InboxData {
  records: InboxRecord[];
  searchActive: boolean;
  resultCount: number | null;
}

export interface ReviewSegment {
  category: string;
  label: string;
  color: string;
  pct: number;
  time: string;
}

export interface ReviewHighlight {
  tag: string;
  tBg: string;
  tFg: string;
  title: string;
  value: string;
  time: string;
  color: string;
  empty: boolean;
}

export interface ReviewStat {
  label: string;
  value: string;
  unit: string;
}

export interface ReviewStatGroup {
  empty: boolean;
  note: string;
  stats: ReviewStat[];
}

export interface ReviewData {
  composition: { total: string; segments: ReviewSegment[] };
  highlights: ReviewHighlight[];
  suggestion: string;
  flow: ReviewStatGroup;
  focus: ReviewStatGroup;
}

export interface RuleItem {
  priority: number;
  category: string;
  ruleType: string;
  key: string;
  value: string;
}

export interface RulesData {
  items: RuleItem[];
  total: number;
  error?: string;
}

export interface RuleSuggestion {
  target: string;
  timeLabel: string;
  displayTarget: string;
}

export interface WeekdayBar {
  day: string;
  seconds: number;
  pct: number;
  isWeekend: boolean;
}

export interface TrendPoint {
  day: string;
  score: number;
}

export interface HeatmapRow {
  day: string;
  cells: number[];
}

export interface DailyRow {
  day: string;
  total: string;
  prod: string;
  score: number;
}

export interface TopActivity {
  name: string;
  time: string;
  ratio: number;
  color: string;
}

export interface ReportData {
  period: string;
  periodOptions: string[];
  startIso: string;
  endIso: string;
  weeklyScorePct: number;
  weeklyProgressText: string;
  coachingText: string;
  weekdayText: string;
  weekdayBars: WeekdayBar[];
  insightMain: string;
  insightSub: string;
  hourly: HourlyRow[];
  trend: TrendPoint[];
  heatmap: HeatmapRow[];
  daily: DailyRow[];
  topActivities: TopActivity[];
  error?: string;
}

export interface UpdateInfo {
  hasUpdate: boolean;
  latest: string;
  current: string;
  url: string;
  assetUrl: string;
  error: string;
}

export interface InstallUpdateResult {
  started: boolean;
  error: string;
}

export interface PresetItem {
  key: string;
  value: string;
}

export interface Option {
  value: string;
  label: string;
}

export interface SettingsData {
  dailyGoalMinutes: number;
  weeklyGoalMinutes: number;
  unproductiveLimitMinutes: number;
  workStartHour: number;
  workEndHour: number;
  profile: string;
  profileOptions: Option[];
  presetItems: PresetItem[];
  excludeSelf: boolean;
  notificationsEnabled: boolean;
  autoBackupEnabled: boolean;
  startupEnabled: boolean;
  storeDomainOnly: boolean;
  storeWindowTitles: boolean;
  retentionDays: number;
  theme: 'light' | 'dark';
  notificationStatus: string;
  diagnosticInfo: string;
  diagnosticResults: string;
  error?: string;
}
