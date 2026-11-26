import { useState } from 'react';
import type { AIModelList, AIProvider, AIService, AISettingsInput, AITestResult, InstallUpdateResult, SettingsData, TrackingOptions, UpdateInfo } from '../types';
import Toggle from './Toggle';
import PresetSection from './PresetSection';
import type { PresetHandlers } from './PresetSection';

export type SettingsTab = 'general' | 'ai' | 'data' | 'help';

const SETTINGS_TABS: { key: SettingsTab; label: string }[] = [
  { key: 'general', label: '일반' },
  { key: 'ai', label: 'AI 분석' },
  { key: 'data', label: '개인정보 · 데이터' },
  { key: 'help', label: '진단 · 도움말' },
];

const PERIOD_OPTIONS = ['최근 7일', '최근 30일', '이번 달'];

interface SettingsProps {
  data: SettingsData;
  tab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
  onSave: (payload: Record<string, unknown>) => void;
  onToggleAutoBackup: (enabled: boolean) => void;
  onToggleStartup: (enabled: boolean) => void;
  onSaveTracking: (changes: TrackingOptions) => void;
  onToggleNotifications: (enabled: boolean) => void;
  onToggleTheme: (theme: 'light' | 'dark') => void;
  onSetProfile: (profile: string) => void;
  onApplyPreset: () => void;
  onCreatePreset: PresetHandlers['onCreatePreset'];
  onUpdatePreset: PresetHandlers['onUpdatePreset'];
  onDeletePreset: PresetHandlers['onDeletePreset'];
  onRunDiagnostics: () => void;
  onExportCsv: () => void;
  onExportCsvPeriod: (period: string) => void;
  onExportBackup: () => void;
  onRestoreBackup: () => void;
  onCheckUpdate: () => Promise<UpdateInfo>;
  onInstallUpdate: (assetUrl: string) => Promise<InstallUpdateResult>;
  onExportLogs: () => void;
  onSaveAiSettings: (input: AISettingsInput) => void;
  onSetAiApiKey: (service: string, apiKey: string, baseUrl: string) => void;
  onClearAiApiKey: (service: string, baseUrl: string) => void;
  onListAiModels: (service: string, baseUrl: string) => Promise<AIModelList>;
  onAddAiExclusion: (value: string) => void;
  onRemoveAiExclusion: (value: string) => void;
  onTestAiConnection: () => Promise<AITestResult>;
}

function ApiKeyField({
  label,
  hasKey,
  placeholder,
  disabled,
  onSave,
  onClear,
}: {
  label: string;
  hasKey: boolean;
  placeholder: string;
  disabled?: boolean;
  onSave: (apiKey: string) => void;
  onClear: () => void;
}) {
  const [apiKey, setApiKey] = useState('');

  const save = () => {
    if (disabled || !apiKey.trim()) return;
    onSave(apiKey);
    setApiKey('');
  };

  return (
    <>
      <label className="tm-settings-field-label" htmlFor="ai-api-key">
        {label} {hasKey && <span style={{ color: 'var(--tm-ok)', fontWeight: 700 }}>· 저장됨</span>}
      </label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <input
          id="ai-api-key"
          className="tm-rule-input"
          type="password"
          autoComplete="off"
          spellCheck={false}
          disabled={disabled}
          placeholder={hasKey ? '새 키로 교체하려면 입력' : placeholder}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') save();
          }}
        />
        <button className="tm-btn-small tm-btn-primary" type="button" onClick={save} disabled={disabled || !apiKey.trim()}>
          키 저장
        </button>
        {hasKey && (
          <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onClear}>
            키 삭제
          </button>
        )}
      </div>
      <div className="tm-settings-help" style={{ maxWidth: 'none', marginBottom: 10 }}>
        키는 Windows 자격 증명 관리자에 저장되며, 설정 파일이나 화면에는 다시 표시되지 않습니다.
      </div>
    </>
  );
}

type AiCardProps = Pick<
  SettingsProps,
  'data' | 'onSaveAiSettings' | 'onSetAiApiKey' | 'onClearAiApiKey' | 'onTestAiConnection' | 'onListAiModels'
>;

/** 서비스 하나의 설정. 서비스마다 다시 마운트해 입력 중인 값이 섞이지 않음. */
function ServiceForm({
  service,
  active,
  onSaveAiSettings,
  onSetAiApiKey,
  onClearAiApiKey,
  onListAiModels,
}: Omit<AiCardProps, 'data' | 'onTestAiConnection'> & { service: AIService; active: boolean }) {
  const [baseUrl, setBaseUrl] = useState(service.baseUrl);
  const [model, setModel] = useState(service.model);
  const [listed, setListed] = useState<string[]>([]);
  const [listing, setListing] = useState(false);
  const [listError, setListError] = useState('');

  const trimmedUrl = baseUrl.trim().replace(/\/+$/, '');
  const urlSaved = trimmedUrl === service.baseUrl;
  const hasKey = urlSaved && service.hasKey;
  const unchanged = active && urlSaved && model.trim() === service.model;
  const options = listed.length > 0 ? listed.map((id) => ({ value: id, label: id })) : service.suggestedModels;
  const ready = !!trimmedUrl && !!model.trim() && (!service.keyRequired || hasKey);

  const loadModels = async () => {
    setListing(true);
    setListError('');
    try {
      const result = await onListAiModels(service.value, trimmedUrl);
      setListed(result.models);
      setListError(result.error);
    } finally {
      setListing(false);
    }
  };

  return (
    <>
      <div className="tm-settings-help" style={{ maxWidth: 'none', marginBottom: 10 }}>
        {service.help}
      </div>

      {service.editableUrl && (
        <>
          <label className="tm-settings-field-label" htmlFor="ai-base-url">
            서버 주소 (Base URL)
          </label>
          <div style={{ display: 'flex', marginBottom: 4 }}>
            <input
              id="ai-base-url"
              className="tm-rule-input"
              placeholder="https://서버주소/v1"
              spellCheck={false}
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value);
                setListed([]);
                setListError('');
              }}
            />
          </div>
          <div className="tm-settings-help" style={{ maxWidth: 'none', marginBottom: 10 }}>
            내 PC(localhost)가 아닌 서버는 https만 사용할 수 있어요.
          </div>
        </>
      )}

      <ApiKeyField
        label={service.keyRequired ? 'API 키' : 'API 키 (필요한 서버만)'}
        placeholder={service.keyPlaceholder || '키가 없으면 비워두세요'}
        disabled={!trimmedUrl}
        hasKey={hasKey}
        onSave={(key) => onSetAiApiKey(service.value, key, trimmedUrl)}
        onClear={() => onClearAiApiKey(service.value, trimmedUrl)}
      />

      <label className="tm-settings-field-label" htmlFor="ai-model">
        모델
      </label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <input
          id="ai-model"
          className="tm-rule-input"
          placeholder="모델 이름 입력 또는 목록에서 선택"
          spellCheck={false}
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
        <button
          className="tm-btn-small tm-btn-ghost"
          type="button"
          onClick={loadModels}
          disabled={listing || !trimmedUrl || (service.keyRequired && !hasKey)}
        >
          {listing ? '불러오는 중…' : '모델 목록 불러오기'}
        </button>
      </div>
      {options.length > 0 && (
        <div className="tm-settings-field-row">
          <select
            className="tm-select"
            aria-label="모델 목록"
            value={options.some((o) => o.value === model) ? model : ''}
            onChange={(e) => e.target.value && setModel(e.target.value)}
          >
            <option value="">{listed.length > 0 ? `모델 ${listed.length}개 중에서 선택` : '추천 모델에서 선택'}</option>
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}
      {listError && <div className="tm-rule-error">{listError}</div>}

      {!unchanged && (
        <button
          className="tm-btn-small tm-btn-primary"
          type="button"
          style={{ marginTop: 4 }}
          disabled={!ready}
          onClick={() =>
            onSaveAiSettings({ provider: 'model', service: service.value, model: model.trim(), baseUrl: trimmedUrl })
          }
        >
          저장하고 사용
        </button>
      )}
    </>
  );
}

function AiSettingsCard({
  data,
  onSaveAiSettings,
  onSetAiApiKey,
  onClearAiApiKey,
  onTestAiConnection,
  onListAiModels,
}: AiCardProps) {
  // 설정 중인 대상. 저장해야 적용됨.
  const [view, setView] = useState<AIProvider>(data.aiProvider);
  const [serviceId, setServiceId] = useState(data.aiService);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AITestResult | null>(null);

  // 다른 곳의 변경을 반영 (예: 백업 복원 시 내장 분석으로 전환)
  const [seenProvider, setSeenProvider] = useState(data.aiProvider);
  if (seenProvider !== data.aiProvider) {
    setSeenProvider(data.aiProvider);
    setView(data.aiProvider);
    setServiceId(data.aiService);
    setTestResult(null);
  }

  const service = data.aiServices.find((s) => s.value === serviceId) ?? data.aiServices[0];
  const active = data.aiProvider === 'model' && data.aiService === service.value;
  const activeService = data.aiServices.find((s) => s.value === data.aiService);
  const activeLabel =
    data.aiProvider === 'model' && activeService ? `${activeService.label} · ${activeService.model}` : '내장 분석';

  const changeView = (next: AIProvider) => {
    setView(next);
    setTestResult(null);
    if (next === 'local') onSaveAiSettings({ provider: 'local', service: '', model: '', baseUrl: '' });
  };

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await onTestAiConnection());
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="tm-card">
      <div className="tm-card-title" style={{ marginBottom: 6 }}>
        분류 추천 · 코칭 방식
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--tm-ink-4)', marginBottom: 12, lineHeight: 1.5 }}>
        기본인 <b>내장 분석</b>은 무료이며 아무것도 전송하지 않아요. 개인 모델을 사용하면
        <b> 앱 이름·도메인과 집계된 시간 통계</b>가 선택한 서비스의 서버로 전송됩니다. 창 제목과 전체 URL은 보내지 않습니다.
      </div>
      <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--tm-ok)', marginBottom: 10 }}>현재 사용 중: {activeLabel}</div>

      <label className="tm-settings-field-label" htmlFor="ai-provider">
        분석 방식
      </label>
      <div className="tm-settings-field-row">
        <select id="ai-provider" className="tm-select" value={view} onChange={(e) => changeView(e.target.value as AIProvider)}>
          {data.aiProviderOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {view === 'local' && (
        <div className="tm-settings-help" style={{ maxWidth: 'none' }}>
          분류 추천은 이 PC의 분류 기록·규칙·직업 프리셋을 학습해 만듭니다. 기록이 적으면 추천이 적게 나오며,
          확실하지 않은 항목은 추천하지 않아요. 코칭은 통계를 바탕으로 한 분석입니다.
        </div>
      )}

      {view === 'model' && (
        <>
          <label className="tm-settings-field-label" htmlFor="ai-service">
            서비스
          </label>
          <div className="tm-settings-field-row">
            <select
              id="ai-service"
              className="tm-select"
              value={service.value}
              onChange={(e) => {
                setServiceId(e.target.value);
                setTestResult(null);
              }}
            >
              {data.aiServices.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          <ServiceForm
            key={service.value}
            service={service}
            active={active}
            onSaveAiSettings={(input) => {
              setTestResult(null);
              onSaveAiSettings(input);
            }}
            onSetAiApiKey={onSetAiApiKey}
            onClearAiApiKey={onClearAiApiKey}
            onListAiModels={onListAiModels}
          />

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
            <span style={{ fontSize: 11.5, fontWeight: 700, color: active ? '#6F9A7C' : 'var(--tm-danger)' }}>
              {active ? '사용 중' : '아직 적용되지 않았어요'}
            </span>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={test} disabled={!active || testing}>
              {testing ? '확인 중…' : '연결 테스트'}
            </button>
            {testResult && (
              <span style={{ fontSize: 11.5, color: testResult.ok ? '#6F9A7C' : 'var(--tm-danger)' }}>{testResult.message}</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function AiExclusionCard({
  entries,
  onAdd,
  onRemove,
}: {
  entries: string[];
  onAdd: (value: string) => void;
  onRemove: (value: string) => void;
}) {
  const [value, setValue] = useState('');

  const add = () => {
    if (!value.trim()) return;
    onAdd(value);
    setValue('');
  };

  return (
    <div className="tm-card">
      <div className="tm-card-title" style={{ marginBottom: 6 }}>
        AI 전송 제외 목록
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--tm-ink-4)', marginBottom: 10, lineHeight: 1.5 }}>
        여기에 넣은 앱·도메인의 <b>이름</b>은 개인 모델에 보내지 않아요. 도메인은 하위 도메인까지 포함합니다. 해당 사용
        시간은 분류별 합계 숫자에는 포함돼요. 질문란에 직접 입력한 글은 그대로 전송됩니다. 내장 분석에는 적용하지 않아요.
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
        <input
          className="tm-rule-input"
          aria-label="전송에서 제외할 앱 또는 도메인"
          placeholder="예: company.com 또는 slack.exe"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.nativeEvent.isComposing) add();
          }}
        />
        <button className="tm-btn-small tm-btn-primary" type="button" onClick={add} disabled={!value.trim()}>
          추가
        </button>
      </div>
      {entries.length === 0 && <div className="tm-empty-row">제외한 항목이 없습니다.</div>}
      {entries.map((entry) => (
        <div key={entry} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderTop: '1px solid var(--tm-line)' }}>
          <span style={{ flex: 1, fontSize: 12, fontWeight: 700, color: 'var(--tm-ink)', wordBreak: 'break-all' }}>{entry}</span>
          <button className="tm-btn-small tm-btn-ghost" type="button" aria-label={`${entry} 제외 해제`} onClick={() => onRemove(entry)}>
            삭제
          </button>
        </div>
      ))}
    </div>
  );
}

function TrackingCard({ data, onSave }: { data: SettingsData; onSave: (changes: TrackingOptions) => void }) {
  const [idleMinutes, setIdleMinutes] = useState<number | ''>(data.idleMinutes);
  const [syncedWith, setSyncedWith] = useState(data.idleMinutes);
  if (data.idleMinutes !== syncedWith) {
    setSyncedWith(data.idleMinutes);
    setIdleMinutes(data.idleMinutes);
  }

  const options: Array<{ key: 'closeToTray' | 'recordMedia' | 'trimIdleTime'; label: string; help: string }> = [
    {
      key: 'closeToTray',
      label: '창을 닫아도 계속 기록',
      help: '창을 닫으면 트레이(작업 표시줄 오른쪽)에 남아요. 끝내려면 트레이 아이콘의 "종료"를 누르세요.',
    },
    {
      key: 'recordMedia',
      label: '영상·회의 중에는 입력이 없어도 기록',
      help: '보고 있는 앱에서 소리가 나고 화면 켜짐이 유지될 때만 기록해요. 입력 없이 3시간이 지나면 멈춰요. 소리를 끈 영상은 알 수 없어요.',
    },
    {
      key: 'trimIdleTime',
      label: '자리를 비운 시간 빼기',
      help: '자리 비움이 되면 마지막 입력 뒤에 기록한 시간도 지워요. 입력 없이 글을 읽은 시간도 함께 빠져요.',
    },
  ];

  return (
    <div className="tm-card">
      <div className="tm-card-title" style={{ marginBottom: 10 }}>
        기록 방식
      </div>
      {options.map((option) => (
        <div className="tm-settings-row" key={option.key} style={{ borderTop: '1px solid var(--tm-line)' }}>
          <div>
            <span className="tm-settings-row-label">{option.label}</span>
            <div className="tm-settings-help">{option.help}</div>
          </div>
          <Toggle label={option.label} checked={data[option.key]} onChange={(enabled) => onSave({ [option.key]: enabled })} />
        </div>
      ))}
      <label className="tm-settings-field-label" htmlFor="idle-minutes" style={{ marginTop: 11 }}>
        자리 비움 기준(입력이 없는 시간, 1~60분)
      </label>
      <div className="tm-settings-field-row" style={{ gap: 8, alignItems: 'center' }}>
        <input
          id="idle-minutes"
          className="tm-settings-number-input"
          type="number"
          min={1}
          max={60}
          style={{ flex: 'none', width: 90 }}
          value={idleMinutes}
          onChange={(e) => setIdleMinutes(e.target.value === '' ? '' : Number(e.target.value))}
        />
        <button className="tm-btn-small tm-btn-primary" type="button" onClick={() => onSave({ idleMinutes })}>
          기준 저장
        </button>
      </div>
    </div>
  );
}

export default function Settings({
  data,
  tab,
  onTabChange,
  onSave,
  onToggleAutoBackup,
  onToggleStartup,
  onSaveTracking,
  onToggleNotifications,
  onToggleTheme,
  onSetProfile,
  onApplyPreset,
  onCreatePreset,
  onUpdatePreset,
  onDeletePreset,
  onRunDiagnostics,
  onExportCsv,
  onExportCsvPeriod,
  onExportBackup,
  onRestoreBackup,
  onCheckUpdate,
  onInstallUpdate,
  onExportLogs,
  onSaveAiSettings,
  onSetAiApiKey,
  onClearAiApiKey,
  onTestAiConnection,
  onListAiModels,
  onAddAiExclusion,
  onRemoveAiExclusion,
}: SettingsProps) {
  const [csvPeriod, setCsvPeriod] = useState(PERIOD_OPTIONS[0]);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [installingUpdate, setInstallingUpdate] = useState(false);
  const [installError, setInstallError] = useState('');

  const handleCheckUpdate = async () => {
    setCheckingUpdate(true);
    setUpdateInfo(null);
    setInstallError('');
    try {
      setUpdateInfo(await onCheckUpdate());
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleInstallUpdate = async () => {
    if (!updateInfo?.assetUrl) return;
    setInstallingUpdate(true);
    setInstallError('');
    try {
      const result = await onInstallUpdate(updateInfo.assetUrl);
      if (!result.started) {
        setInstallError(result.error || '업데이트 설치를 시작하지 못했습니다.');
        setInstallingUpdate(false);
      }
    } catch (error) {
      setInstallingUpdate(false);
      throw error;
    }
    // 성공하면 앱이 스스로 종료하고 설치 프로그램에 넘김
    // → 이후 상태 갱신 불필요
  };
  const saved = {
    dailyGoalMinutes: data.dailyGoalMinutes,
    weeklyGoalMinutes: data.weeklyGoalMinutes,
    unproductiveLimitMinutes: data.unproductiveLimitMinutes,
    workStartHour: data.workStartHour,
    workEndHour: data.workEndHour,
    retentionDays: data.retentionDays,
  };
  type FormKey = keyof typeof saved;
  // 입력 중에는 빈칸 허용, 저장 시 백엔드가 거절
  const [form, setForm] = useState<Record<FormKey, number | ''>>(saved);
  const [syncedWith, setSyncedWith] = useState(saved);
  const [confirmRetention, setConfirmRetention] = useState(false);
  // 저장·복원된 값만 반영, 저장 안 한 다른 입력은 유지
  const changedKeys = (Object.keys(saved) as FormKey[]).filter((key) => saved[key] !== syncedWith[key]);
  if (changedKeys.length > 0) {
    setSyncedWith(saved);
    setForm((prev) => ({ ...prev, ...Object.fromEntries(changedKeys.map((key) => [key, saved[key]])) }));
  }

  const field = (key: FormKey) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      if (key === 'retentionDays') setConfirmRetention(false);
      setForm((prev) => ({ ...prev, [key]: e.target.value === '' ? '' : Number(e.target.value) }));
    },
  });

  // 버튼마다 자기 항목만 전송, 나머지는 저장된 값 유지
  const saveGoals = () => onSave({ ...form, retentionDays: data.retentionDays });
  const savePrivacy = (changes: Record<string, unknown>) =>
    onSave({ ...saved, storeDomainOnly: data.storeDomainOnly, storeWindowTitles: data.storeWindowTitles, ...changes });

  // 보존 기간 단축은 기록을 삭제하므로 두 번 눌러야 함
  const deletesRecords =
    typeof form.retentionDays === 'number' &&
    form.retentionDays > 0 &&
    (data.retentionDays === 0 || form.retentionDays < data.retentionDays);
  const saveRetention = () => {
    if (deletesRecords && !confirmRetention) {
      setConfirmRetention(true);
      return;
    }
    setConfirmRetention(false);
    savePrivacy({ retentionDays: form.retentionDays });
  };

  const panel = (key: SettingsTab) => ({
    id: `settings-panel-${key}`,
    role: 'tabpanel',
    'aria-labelledby': `settings-tab-${key}`,
    className: 'tm-tab-panel',
    hidden: tab !== key,
  });

  return (
    <div className="tm-page">
      <div className="tm-tabs" role="tablist" aria-label="설정 구분">
        {SETTINGS_TABS.map((item, index) => (
          <button
            key={item.key}
            id={`settings-tab-${item.key}`}
            className="tm-tab"
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            aria-controls={`settings-panel-${item.key}`}
            tabIndex={tab === item.key ? 0 : -1}
            onClick={() => onTabChange(item.key)}
            onKeyDown={(e) => {
              const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
              if (!step) return;
              e.preventDefault();
              const next = SETTINGS_TABS[(index + step + SETTINGS_TABS.length) % SETTINGS_TABS.length];
              onTabChange(next.key);
              document.getElementById(`settings-tab-${next.key}`)?.focus();
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {data.error && <div className="tm-rule-error" role="alert">{data.error}</div>}

      {/* 패널은 계속 마운트: 탭을 바꿔도 저장 안 한 입력 유지 */}
      <div {...panel('general')}>
        <div className="tm-settings-2col">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 15 }}>
            목표 · 근무 시간
          </div>
          <label className="tm-settings-field-label" htmlFor="daily-goal">일간 생산 목표(분)</label>
          <div className="tm-settings-field-row">
            <input id="daily-goal" className="tm-settings-number-input" type="number" min={1} {...field('dailyGoalMinutes')} />
          </div>
          <label className="tm-settings-field-label" htmlFor="weekly-goal">주간 생산 목표(분)</label>
          <div className="tm-settings-field-row">
            <input id="weekly-goal" className="tm-settings-number-input" type="number" min={1} {...field('weeklyGoalMinutes')} />
          </div>
          <label className="tm-settings-field-label" htmlFor="unproductive-limit">비생산 상한(분)</label>
          <div className="tm-settings-field-row">
            <input id="unproductive-limit" className="tm-settings-number-input" type="number" min={1} {...field('unproductiveLimitMinutes')} />
          </div>
          <div className="tm-settings-help" style={{ maxWidth: 'none' }}>
            알림: 비생산 활동이 쉬지 않고 이만큼 이어질 때(1분 이하의 다른 창 전환은 이어진 것으로 봐요). 코칭: 하루에 쓴
            합계가 이 값을 넘었는지 알려줘요.
          </div>
          <label className="tm-settings-field-label">근무 시간</label>
          <div className="tm-settings-field-row" style={{ alignItems: 'center' }}>
            <input className="tm-settings-number-input" type="number" aria-label="근무 시작 시각" min={0} max={23} {...field('workStartHour')} />
            <span style={{ color: 'var(--tm-muted)' }}>–</span>
            <input className="tm-settings-number-input" type="number" aria-label="근무 종료 시각" min={1} max={24} {...field('workEndHour')} />
          </div>
          <div className="tm-settings-help" style={{ maxWidth: 'none' }}>
            종료 시각에 하루 마무리 알림을 보내요. 시작 시각은 개인 모델 코칭의 참고 정보로만 써요.
          </div>
          <button className="tm-btn-small tm-btn-primary" type="button" style={{ marginTop: 12 }} onClick={saveGoals}>
            목표 저장
          </button>
        </div>
        <div className="tm-card">
          <div className="tm-card-title">직업 프리셋</div>
          <div style={{ fontSize: 11.5, color: 'var(--tm-ink-4)', margin: '3px 0 13px' }}>
            직업을 선택하면 추천 분류 규칙 후보가 표시돼요. 직접 만들거나 복제해서 바꿀 수도 있어요. 적용 전까지는 실제로 분류되지 않습니다.
          </div>
          <PresetSection
            data={data}
            onSetProfile={onSetProfile}
            onApplyPreset={onApplyPreset}
            onCreatePreset={onCreatePreset}
            onUpdatePreset={onUpdatePreset}
            onDeletePreset={onDeletePreset}
          />
          <div className="tm-settings-row" style={{ borderTop: '1px solid var(--tm-line)' }}>
            <div>
              <span className="tm-settings-row-label">목표·집중 알림 표시</span>
              <div className="tm-settings-help">{data.notificationStatus}</div>
            </div>
            <Toggle label="목표·집중 알림 표시" checked={data.notificationsEnabled} onChange={onToggleNotifications} />
          </div>
          <div className="tm-settings-row">
            <span className="tm-settings-row-label">다크 모드</span>
            <Toggle label="다크 모드" checked={data.theme === 'dark'} onChange={(enabled) => onToggleTheme(enabled ? 'dark' : 'light')} />
          </div>
          <div className="tm-settings-row">
            <span className="tm-settings-row-label">주 1회 자동 백업</span>
            <Toggle label="주 1회 자동 백업" checked={data.autoBackupEnabled} onChange={onToggleAutoBackup} />
          </div>
          <div className="tm-settings-row">
            <div>
              <span className="tm-settings-row-label">Windows 시작 시 자동 실행</span>
              <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginTop: 1 }}>로그인하면 창 없이 트레이에서 기록을 시작해요.</div>
            </div>
            <Toggle label="Windows 시작 시 자동 실행" checked={data.startupEnabled} onChange={onToggleStartup} />
          </div>
        </div>
        <TrackingCard data={data} onSave={onSaveTracking} />
        </div>
      </div>

      <div {...panel('ai')}>
        <AiSettingsCard
          data={data}
          onSaveAiSettings={onSaveAiSettings}
          onSetAiApiKey={onSetAiApiKey}
          onClearAiApiKey={onClearAiApiKey}
          onTestAiConnection={onTestAiConnection}
          onListAiModels={onListAiModels}
        />
        <AiExclusionCard entries={data.aiExcludedTargets} onAdd={onAddAiExclusion} onRemove={onRemoveAiExclusion} />
      </div>

      <div {...panel('data')}>
        <div className="tm-settings-2col">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 8 }}>
            개인정보
          </div>
          <div className="tm-settings-row" style={{ borderTop: '1px solid var(--tm-line)' }}>
            <div>
              <div className="tm-settings-row-label">URL은 도메인만 저장</div>
              <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginTop: 1 }}>전체 경로·검색어 대신 도메인만 기록해요. 바꾼 뒤의 기록부터 적용돼요.</div>
            </div>
            <Toggle label="URL은 도메인만 저장" checked={data.storeDomainOnly} onChange={(v) => savePrivacy({ storeDomainOnly: v })} />
          </div>
          <div className="tm-settings-row">
            <div>
              <div className="tm-settings-row-label">창 제목 저장</div>
              <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginTop: 1 }}>문서·탭 제목까지 기록해요.</div>
            </div>
            <Toggle label="창 제목 저장" checked={data.storeWindowTitles} onChange={(v) => savePrivacy({ storeWindowTitles: v })} />
          </div>
          <label className="tm-settings-field-label" htmlFor="retention-days" style={{ marginTop: 11 }}>
            데이터 보존 기간(일, 0=무제한)
          </label>
          <div className="tm-settings-field-row">
            <input id="retention-days" className="tm-settings-number-input" type="number" min={0} style={{ flex: 'none', width: 90 }} {...field('retentionDays')} />
          </div>
          <div className="tm-settings-help" style={{ maxWidth: 'none' }}>
            0이 아니면, 보존 기간이 지난 기록은 앱을 시작할 때와 켜 둔 채 날짜가 바뀔 때 삭제돼요.
          </div>
          <button className="tm-btn-small tm-btn-primary" type="button" style={{ marginTop: 12 }} onClick={saveRetention}>
            {confirmRetention ? '오래된 기록 삭제에 동의하고 저장' : '보존 기간 저장'}
          </button>
          {confirmRetention && (
            <div className="tm-rule-error" role="alert" style={{ marginTop: 8, marginBottom: 0 }}>
              다음에 앱을 시작하거나 날짜가 바뀌면 {form.retentionDays}일보다 오래된 활동 기록과 코칭이 삭제되며 되돌릴 수 없어요. 필요하면
              먼저 백업을 내보내세요. 계속하려면 버튼을 한 번 더 누르세요.
            </div>
          )}
        </div>
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 10 }}>
            내보내기 · 백업
          </div>
          <div className="tm-settings-field-label">활동 기록을 CSV 파일로</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onExportCsv}>
              오늘 CSV
            </button>
            <select
              className="tm-select"
              aria-label="CSV 기간"
              value={csvPeriod}
              onChange={(e) => setCsvPeriod(e.target.value)}
            >
              {PERIOD_OPTIONS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => onExportCsvPeriod(csvPeriod)}>
              기간 CSV 내보내기
            </button>
          </div>
          <div className="tm-settings-field-label">전체 데이터 백업</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            <button className="tm-btn-small tm-btn-primary" type="button" onClick={onExportBackup}>
              백업 내보내기
            </button>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onRestoreBackup}>
              백업 복원
            </button>
          </div>
          <div className="tm-settings-help" style={{ maxWidth: 'none' }}>
            복원하면 활동 기록·규칙·설정이 백업 시점으로 바뀝니다. 복원 직전 상태는 자동으로 따로 보관해요.
          </div>
        </div>
        </div>
      </div>

      <div {...panel('help')}>
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 6 }}>
            진단 정보
          </div>
          <pre style={{ fontSize: 11, color: 'var(--tm-ink-4)', whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: '4px 0' }}>
            {data.diagnosticInfo}
          </pre>
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <button className="tm-btn-small tm-btn-primary" type="button" onClick={onRunDiagnostics}>
              진단 실행
            </button>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={handleCheckUpdate} disabled={checkingUpdate}>
              {checkingUpdate ? '확인 중…' : '업데이트 확인'}
            </button>
          </div>
          {updateInfo && (
            <div style={{ marginTop: 8, fontSize: 11.5 }}>
              {updateInfo.error ? (
                <span style={{ color: 'var(--tm-danger)' }}>{updateInfo.error}</span>
              ) : updateInfo.hasUpdate ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ color: 'var(--tm-ok)', fontWeight: 700 }}>새 버전 v{updateInfo.latest} 출시</span>
                  {updateInfo.assetUrl ? (
                    <button
                      className="tm-btn-small tm-btn-primary"
                      type="button"
                      onClick={handleInstallUpdate}
                      disabled={installingUpdate}
                    >
                      {installingUpdate ? '설치 준비 중…' : '지금 설치'}
                    </button>
                  ) : (
                    <a href={updateInfo.url} target="_blank" rel="noreferrer" style={{ color: 'var(--tm-ok)' }}>
                      다운로드
                    </a>
                  )}
                </div>
              ) : (
                <span style={{ color: 'var(--tm-ink-4)' }}>최신 버전입니다 (v{updateInfo.current})</span>
              )}
              {installError && (
                <div style={{ color: 'var(--tm-danger)', marginTop: 6 }}>{installError}</div>
              )}
            </div>
          )}
          {data.diagnosticResults && (
            <pre style={{ fontSize: 11, color: 'var(--tm-ink-3)', whiteSpace: 'pre-wrap', fontFamily: 'inherit', marginTop: 8 }}>
              {data.diagnosticResults}
            </pre>
          )}

          <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--tm-line)' }}>
            <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--tm-ink-3)', marginBottom: 6 }}>문제 신고</div>
            <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginBottom: 8 }}>
              버그를 발견하셨나요? 로그를 내보내고 구글폼에 신고해주세요.
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                className="tm-btn-small tm-btn-ghost"
                type="button"
                onClick={() => navigator.clipboard.writeText(data.diagnosticInfo)}
                aria-label="진단 정보 클립보드 복사"
              >
                진단 정보 복사
              </button>
              <button
                className="tm-btn-small tm-btn-ghost"
                type="button"
                onClick={onExportLogs}
                aria-label="로그 파일 바탕화면에 내보내기"
              >
                로그 내보내기
              </button>
              <a
                href="https://docs.google.com/forms/d/e/1FAIpQLSc3P-8LfIng9NUMfu3rNOsP4t22LYyjAURxBZjGadKLY1QMgQ/viewform?usp=publish-editor"
                target="_blank"
                rel="noreferrer"
                className="tm-btn-small tm-btn-primary"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}
                aria-label="문제 신고하기"
              >
                문제 신고하기
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
