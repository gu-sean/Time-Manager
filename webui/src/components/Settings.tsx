import { useState } from 'react';
import type { SettingsData, UpdateInfo } from '../types';
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
  onExportLogs: () => void;
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
  onExportLogs,
}: SettingsProps) {
  const [csvPeriod, setCsvPeriod] = useState(PERIOD_OPTIONS[0]);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);

  const handleCheckUpdate = async () => {
    setCheckingUpdate(true);
    setUpdateInfo(null);
    const result = await onCheckUpdate();
    setUpdateInfo(result);
    setCheckingUpdate(false);
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
          <div style={{ fontSize: 11.5, color: '#918B80', margin: '3px 0 13px' }}>
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
          <div className="tm-settings-row" style={{ borderTop: '1px solid #F0ECE3' }}>
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
          <div className="tm-settings-row" style={{ borderTop: '1px solid #F0ECE3' }}>
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
          <pre style={{ fontSize: 11, color: '#8A8377', whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: '4px 0' }}>
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
                <span style={{ color: '#6F9A7C', fontWeight: 700 }}>
                  새 버전 v{updateInfo.latest} 출시 —{' '}
                  <a href={updateInfo.url} target="_blank" rel="noreferrer" style={{ color: '#6F9A7C' }}>
                    다운로드
                  </a>
                </span>
              ) : (
                <span style={{ color: '#918B80' }}>최신 버전입니다 (v{updateInfo.current})</span>
              )}
            </div>
          )}
          {data.diagnosticResults && (
            <pre style={{ fontSize: 10.5, color: '#6E6759', whiteSpace: 'pre-wrap', fontFamily: 'inherit', marginTop: 8 }}>
              {data.diagnosticResults}
            </pre>
          )}

          <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #F0ECE3' }}>
            <div style={{ fontSize: 11.5, fontWeight: 700, color: '#6E6759', marginBottom: 6 }}>문제 신고</div>
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
