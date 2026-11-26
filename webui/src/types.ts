export interface StatCard {
  key: string;
  label: string;
  value: string;
  /** 예: "▲ 34분", "변화 없음" */
  delta: string;
  /** good: 바람직한 변화, bad: 바람직하지 않은 변화, neutral: 판단하지 않음·변화 없음 */
  tone: 'good' | 'bad' | 'neutral';
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
  goal: DailyGoal;
  /** 시간을 정한 일시정지가 끝나는 때 ("15:30", "내일 00:10"). 아니면 "" */
  pausedUntil: string;
  /** 비교 대상 (예: "어제 같은 시각", "전날") */
  comparedWith: string;
  problem?: string;
  notices?: string[];
  dateLabel: string;
  viewingToday: boolean;
  tracking: boolean;
  stats: StatCard[];
  donut: { total: string; segments: DonutSegment[] };
  hourly: HourlyRow[];
  topApps: TopAppRow[];
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
  detail?: string;
  /** "앞으로도 적용" 규칙에 쓸 사이트·앱. 규칙 효과가 없으면 빈 문자열. */
  ruleTarget?: string;
}

export interface InboxData {
  records: InboxRecord[];
  searchActive: boolean;
  resultCount: number | null;
  truncated?: boolean;
  query: string;
  category: string | null;
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
  /** YYYY-MM-DD */
  date: string;
  score: number;
}

export interface HeatmapRow {
  day: string;
  cells: number[];
  seconds: number[];
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

/** 바꿀 항목만 전송. 자리 비움 기준은 빈칸이면 백엔드가 거절. */
export interface DailyGoal {
  /** 목표를 쉬는 요일 */
  offDay: boolean;
  value: string;
  pct: number;
  ratio: number;
  achieved: boolean;
  remaining: string;
}

export interface RuleReapplyPreview {
  count: number;
  timeLabel: string;
  items: { target: string; from: string; to: string; count: number; timeLabel: string }[];
  more: number;
}

export interface TrackingOptions {
  idleMinutes?: number | '';
  recordMedia?: boolean;
  trimIdleTime?: boolean;
  closeToTray?: boolean;
  focusAlert?: boolean;
}

export interface DeletePreview {
  error: string;
  count: number;
  timeLabel: string;
  /** 사이트·앱 이름 (기간 삭제에는 없음) */
  target?: string;
  kindLabel?: string;
}

export interface ActionResult {
  message: string;
  error: string;
}

export interface ManualEntry {
  start: string;
  minutes: number | '';
  label: string;
  category: string;
}

export interface SettingsData {
  appVersion: string;
  dailyGoalMinutes: number;
  weeklyGoalMinutes: number;
  unproductiveLimitMinutes: number;
  workStartHour: number;
  workEndHour: number;
  profile: string;
  profileOptions: PresetOption[];
  notice?: string;
  presetItems: PresetItem[];
  notificationsEnabled: boolean;
  autoBackupEnabled: boolean;
  startupEnabled: boolean;
  idleMinutes: number;
  recordMedia: boolean;
  trimIdleTime: boolean;
  closeToTray: boolean;
  focusAlert: boolean;
  /** 일간 목표를 적용하는 요일 (월=0 ~ 일=6) */
  goalWeekdays: number[];
  storeDomainOnly: boolean;
  storeWindowTitles: boolean;
  retentionDays: number;
  theme: 'light' | 'dark';
  notificationStatus: string;
  diagnosticInfo: string;
  diagnosticResults: string;
  aiProvider: AIProvider;
  aiProviderOptions: Option[];
  aiService: string;
  aiServices: AIService[];
  aiExcludedTargets: string[];
  error?: string;
}

export interface AIRuleSuggestion {
  target: string;
  displayTarget: string;
  timeLabel: string;
  category: 'productive' | 'unproductive' | 'neutral';
  categoryLabel: string;
  reason: string;
}

export type AIProvider = 'local' | 'model';

export interface AIService {
  value: string;
  label: string;
  help: string;
  editableUrl: boolean;
  keyRequired: boolean;
  keyPlaceholder: string;
  suggestedModels: Option[];
  model: string;
  baseUrl: string;
  hasKey: boolean;
}

export interface AIModelList {
  models: string[];
  error: string;
}

export interface AISettingsInput {
  provider: AIProvider;
  service: string;
  model: string;
  baseUrl: string;
}

export interface AIRequestPreview {
  serviceLabel: string;
  url: string;
  model: string;
  instructions: string;
  data: string;
  error: string;
}

export interface PresetOption {
  value: string;
  label: string;
  emoji: string;
  custom: boolean;
}

export interface CoachingHistoryEntry {
  id: number;
  createdAt: string;
  scope: 'day' | 'week';
  startDay: string;
  endDay: string;
  source: string;
  generated: boolean;
  headline: string;
  insights: string[];
  actions: string[];
}

export interface AskResult {
  answer: string;
  interpretation: string;
  /** ratio: 행의 막대 길이 (0–1) */
  rows: { label: string; time: string; ratio?: number }[];
  note: string;
  source: string;
  error: string;
  canFallback: boolean;
}

export interface AIRuleSuggestionsResult {
  canFallback: boolean;
  excluded: number;
  items: AIRuleSuggestion[];
  skipped: number;
  source: string;
  error: string;
}

export interface AICoaching {
  headline: string;
  insights: string[];
  actions: string[];
  scopeLabel: string;
  source: string;
  generated: boolean;
  canFallback: boolean;
  savedAt?: string;
  reused?: boolean;
  error: string;
}

export interface AITestResult {
  ok: boolean;
  message: string;
}
