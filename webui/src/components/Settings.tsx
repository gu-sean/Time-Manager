import { useState } from 'react';
import type { AIModelList, AIProvider, AIService, AISettingsInput, AITestResult, InstallUpdateResult, SettingsData, UpdateInfo } from '../types';
import Toggle from './Toggle';

const PRESET_EMOJI: Record<string, string> = {
  developer: '💻',
  student: '📚',
  office: '💼',
  creator: '🎨',
  researcher: '🔬',
  designer: '🎨',
  marketer: '📣',
  finance: '💰',
  manager: '📊',
};

const PERIOD_OPTIONS = ['최근 7일', '최근 30일', '이번 달'];

interface SettingsProps {
  data: SettingsData;
  onSave: (payload: Record<string, unknown>) => void;
  onToggleExcludeSelf: (enabled: boolean) => void;
  onToggleAutoBackup: (enabled: boolean) => void;
  onToggleStartup: (enabled: boolean) => void;
  onToggleNotifications: (enabled: boolean) => void;
  onToggleTheme: (theme: 'light' | 'dark') => void;
  onSetProfile: (profile: string) => void;
  onApplyPreset: () => void;
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
        {label} {hasKey && <span style={{ color: '#6F9A7C', fontWeight: 700 }}>· 저장됨</span>}
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

/** Setup of one service. Remounted per service, so its drafts never leak into another. */
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
    const result = await onListAiModels(service.value, trimmedUrl);
    setListed(result.models);
    setListError(result.error);
    setListing(false);
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
  // What is being configured; it becomes active only once saved.
  const [view, setView] = useState<AIProvider>(data.aiProvider);
  const [serviceId, setServiceId] = useState(data.aiService);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<AITestResult | null>(null);

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
    setTestResult(await onTestAiConnection());
    setTesting(false);
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
      <div style={{ fontSize: 11.5, fontWeight: 700, color: '#6F9A7C', marginBottom: 10 }}>현재 사용 중: {activeLabel}</div>

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
            <span style={{ fontSize: 11.5, fontWeight: 700, color: active ? '#6F9A7C' : '#CB8056' }}>
              {active ? '사용 중' : '아직 적용되지 않았어요'}
            </span>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={test} disabled={!active || testing}>
              {testing ? '확인 중…' : '연결 테스트'}
            </button>
            {testResult && (
              <span style={{ fontSize: 11.5, color: testResult.ok ? '#6F9A7C' : '#CB8056' }}>{testResult.message}</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function Settings({
  data,
  onSave,
  onToggleExcludeSelf,
  onToggleAutoBackup,
  onToggleStartup,
  onToggleNotifications,
  onToggleTheme,
  onSetProfile,
  onApplyPreset,
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
    const result = await onCheckUpdate();
    setUpdateInfo(result);
    setCheckingUpdate(false);
  };

  const handleInstallUpdate = async () => {
    if (!updateInfo?.assetUrl) return;
    setInstallingUpdate(true);
    setInstallError('');
    const result = await onInstallUpdate(updateInfo.assetUrl);
    if (!result.started) {
      setInstallError(result.error || '업데이트 설치를 시작하지 못했습니다.');
      setInstallingUpdate(false);
    }
    // On success the app quits itself to hand off to the installer, so no
    // further state update is needed here.
  };
  const [form, setForm] = useState({
    dailyGoalMinutes: data.dailyGoalMinutes,
    weeklyGoalMinutes: data.weeklyGoalMinutes,
    unproductiveLimitMinutes: data.unproductiveLimitMinutes,
    workStartHour: data.workStartHour,
    workEndHour: data.workEndHour,
    retentionDays: data.retentionDays,
  });

  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm((prev) => ({ ...prev, [key]: Number(e.target.value) })),
  });

  return (
    <div className="tm-page">
      <div className="tm-settings-2col">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 15 }}>
            목표 · 근무 시간
          </div>
          <label className="tm-settings-field-label">일간 생산 목표(분)</label>
          <div className="tm-settings-field-row">
            <input className="tm-settings-number-input" type="number" {...field('dailyGoalMinutes')} />
          </div>
          <label className="tm-settings-field-label">주간 생산 목표(분)</label>
          <div className="tm-settings-field-row">
            <input className="tm-settings-number-input" type="number" {...field('weeklyGoalMinutes')} />
          </div>
          <label className="tm-settings-field-label">비생산 제한(분)</label>
          <div className="tm-settings-field-row">
            <input className="tm-settings-number-input" type="number" {...field('unproductiveLimitMinutes')} />
          </div>
          <label className="tm-settings-field-label">근무 시간</label>
          <div className="tm-settings-field-row" style={{ alignItems: 'center' }}>
            <input className="tm-settings-number-input" type="number" {...field('workStartHour')} />
            <span style={{ color: '#B6AFA2' }}>–</span>
            <input className="tm-settings-number-input" type="number" {...field('workEndHour')} />
          </div>
        </div>

        <div className="tm-card">
          <div className="tm-card-title">직업 프리셋</div>
          <div style={{ fontSize: 11.5, color: 'var(--tm-ink-4)', margin: '3px 0 13px' }}>
            직업을 선택하면 추천 분류 규칙 후보가 표시돼요. 적용 전까지는 실제로 분류되지 않습니다.
          </div>
          <div className="tm-preset-grid">
            {data.profileOptions
              .filter((opt) => opt.value)
              .map((opt) => (
                <button
                  key={opt.value}
                  className={`tm-preset-item${data.profile === opt.value ? ' active' : ''}`}
                  type="button"
                  onClick={() => onSetProfile(opt.value)}
                >
                  <span className="tm-preset-emoji">{PRESET_EMOJI[opt.value] ?? '🧩'}</span>
                  <span className="tm-preset-name">{opt.label}</span>
                </button>
              ))}
          </div>
          {data.presetItems.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, color: '#A79F92', marginBottom: 6 }}>
                후보 규칙 {data.presetItems.length}개
              </div>
              <button className="tm-btn-small tm-btn-primary" type="button" onClick={onApplyPreset}>
                선택 규칙 적용
              </button>
            </div>
          )}
          <div className="tm-settings-row" style={{ borderTop: '1px solid var(--tm-line)' }}>
            <span className="tm-settings-row-label">시간 관리자 앱을 기록에서 제외</span>
            <Toggle checked={data.excludeSelf} onChange={onToggleExcludeSelf} />
          </div>
          <div className="tm-settings-row">
            <div>
              <span className="tm-settings-row-label">목표·집중 알림 표시</span>
              <div className="tm-settings-help">{data.notificationStatus}</div>
            </div>
            <Toggle checked={data.notificationsEnabled} onChange={onToggleNotifications} />
          </div>
          <div className="tm-settings-row">
            <span className="tm-settings-row-label">다크 모드</span>
            <Toggle checked={data.theme === 'dark'} onChange={(enabled) => onToggleTheme(enabled ? 'dark' : 'light')} />
          </div>
          <div className="tm-settings-row">
            <span className="tm-settings-row-label">주 1회 자동 백업</span>
            <Toggle checked={data.autoBackupEnabled} onChange={onToggleAutoBackup} />
          </div>
          <div className="tm-settings-row">
            <div>
              <span className="tm-settings-row-label">Windows 시작 시 자동 실행</span>
              <div style={{ fontSize: 10.5, color: '#A79F92', marginTop: 1 }}>로그인할 때 Time Manager를 자동으로 시작해요.</div>
            </div>
            <Toggle checked={data.startupEnabled} onChange={onToggleStartup} />
          </div>
        </div>
      </div>

      <div className="tm-settings-2col">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 8 }}>
            개인정보
          </div>
          <div className="tm-settings-row" style={{ borderTop: '1px solid var(--tm-line)' }}>
            <div>
              <div className="tm-settings-row-label">URL은 도메인만 저장</div>
              <div style={{ fontSize: 10.5, color: '#A79F92', marginTop: 1 }}>전체 경로 대신 도메인만 기록해요.</div>
            </div>
            <Toggle checked={data.storeDomainOnly} onChange={(v) => onSave({ ...form, storeDomainOnly: v, storeWindowTitles: data.storeWindowTitles })} />
          </div>
          <div className="tm-settings-row">
            <div>
              <div className="tm-settings-row-label">창 제목 저장</div>
              <div style={{ fontSize: 10.5, color: '#A79F92', marginTop: 1 }}>문서·탭 제목까지 기록해요.</div>
            </div>
            <Toggle checked={data.storeWindowTitles} onChange={(v) => onSave({ ...form, storeDomainOnly: data.storeDomainOnly, storeWindowTitles: v })} />
          </div>
          <label className="tm-settings-field-label" style={{ marginTop: 11 }}>
            데이터 보존 기간(일, 0=무제한)
          </label>
          <div className="tm-settings-field-row">
            <input className="tm-settings-number-input" type="number" style={{ flex: 'none', width: 90 }} {...field('retentionDays')} />
          </div>
        </div>

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
                <span style={{ color: '#CB8056' }}>{updateInfo.error}</span>
              ) : updateInfo.hasUpdate ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ color: '#6F9A7C', fontWeight: 700 }}>새 버전 v{updateInfo.latest} 출시</span>
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
                    <a href={updateInfo.url} target="_blank" rel="noreferrer" style={{ color: '#6F9A7C' }}>
                      다운로드
                    </a>
                  )}
                </div>
              ) : (
                <span style={{ color: 'var(--tm-ink-4)' }}>최신 버전입니다 (v{updateInfo.current})</span>
              )}
              {installError && (
                <div style={{ color: '#CB8056', marginTop: 6 }}>{installError}</div>
              )}
            </div>
          )}
          {data.diagnosticResults && (
            <pre style={{ fontSize: 10.5, color: 'var(--tm-ink-3)', whiteSpace: 'pre-wrap', fontFamily: 'inherit', marginTop: 8 }}>
              {data.diagnosticResults}
            </pre>
          )}

          <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--tm-line)' }}>
            <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--tm-ink-3)', marginBottom: 6 }}>문제 신고</div>
            <div style={{ fontSize: 11, color: '#A79F92', marginBottom: 8 }}>
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

      <AiSettingsCard
        data={data}
        onSaveAiSettings={onSaveAiSettings}
        onSetAiApiKey={onSetAiApiKey}
        onClearAiApiKey={onClearAiApiKey}
        onTestAiConnection={onTestAiConnection}
        onListAiModels={onListAiModels}
      />

      {data.error && <div className="tm-rule-error">{data.error}</div>}

      <div className="tm-settings-bottom">
        <button className="tm-btn-small tm-btn-primary" type="button" onClick={() => onSave(form)}>
          개인화 저장
        </button>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onExportCsv}>
            오늘 CSV
          </button>
          <div style={{ display: 'flex', gap: 4 }}>
            <select
              className="tm-select"
              value={csvPeriod}
              onChange={(e) => setCsvPeriod(e.target.value)}
              style={{ fontSize: 12, height: 28 }}
            >
              {PERIOD_OPTIONS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => onExportCsvPeriod(csvPeriod)}>
              CSV 내보내기
            </button>
          </div>
          <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onExportBackup}>
            백업 내보내기
          </button>
          <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onRestoreBackup}>
            백업 복원
          </button>
        </div>
      </div>
    </div>
  );
}
