import { useState } from 'react';
import type { PresetItem, PresetOption, SettingsData } from '../types';

const NAME_LENGTH = 30;
const KINDS = [
  { value: 'domains', label: '도메인', placeholder: '예: company.com' },
  { value: 'apps', label: '앱 이름', placeholder: '예: slack.exe' },
  { value: 'title_keywords', label: '창 제목 키워드', placeholder: '예: 회의록' },
];
const SIDES = [
  { value: 'productive', label: '생산적' },
  { value: 'unproductive', label: '비생산적' },
];
const muted = { fontSize: 11, color: 'var(--tm-muted)' } as const;
const row = { display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' } as const;

function describeKey(key: string) {
  const [side, ...kind] = key.split('_');
  return {
    side: SIDES.find((s) => s.value === side)?.label ?? side,
    kind: KINDS.find((k) => k.value === kind.join('_'))?.label ?? key,
  };
}

export interface PresetHandlers {
  onSetProfile: (profile: string) => void;
  onApplyPreset: () => void;
  onCreatePreset: (name: string, emoji: string, source: string) => Promise<SettingsData>;
  onUpdatePreset: (id: string, name: string, emoji: string, items: PresetItem[]) => Promise<SettingsData>;
  onDeletePreset: (id: string) => void;
}

function NameFields({
  name,
  emoji,
  onName,
  onEmoji,
}: {
  name: string;
  emoji: string;
  onName: (value: string) => void;
  onEmoji: (value: string) => void;
}) {
  return (
    <div style={{ ...row, flexWrap: 'nowrap' }}>
      <input
        className="tm-rule-input"
        aria-label="프리셋 아이콘"
        placeholder="🧩"
        maxLength={8}
        value={emoji}
        onChange={(e) => onEmoji(e.target.value)}
        style={{ flex: 'none', width: 52, textAlign: 'center' }}
      />
      <input
        className="tm-rule-input"
        aria-label="프리셋 이름"
        placeholder="프리셋 이름"
        maxLength={NAME_LENGTH}
        value={name}
        onChange={(e) => onName(e.target.value)}
        style={{ minWidth: 0 }}
      />
    </div>
  );
}

function CreateForm({
  selected,
  onCreate,
  onClose,
}: {
  selected: PresetOption | undefined;
  onCreate: PresetHandlers['onCreatePreset'];
  onClose: (created: SettingsData | null) => void;
}) {
  const [name, setName] = useState('');
  const [emoji, setEmoji] = useState('');
  const [source, setSource] = useState(selected?.value ?? '');
  const [error, setError] = useState('');

  const create = async () => {
    const result = await onCreate(name, emoji, source);
    if (result.error) setError(result.error);
    else onClose(result);
  };

  return (
    <div role="group" aria-label="새 프리셋" style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
      <NameFields name={name} emoji={emoji} onName={setName} onEmoji={setEmoji} />
      <select className="tm-select" aria-label="시작할 내용" value={source} onChange={(e) => setSource(e.target.value)}>
        <option value="">빈 프리셋으로 시작</option>
        <option value="current_rules">지금 내 규칙으로 만들기</option>
        {selected?.value && <option value={selected.value}>'{selected.label}' 복제하기</option>}
      </select>
      {error && <div className="tm-rule-error" style={{ marginBottom: 0 }}>{error}</div>}
      <div style={row}>
        <button className="tm-btn-small tm-btn-primary" type="button" onClick={create} disabled={!name.trim()}>
          만들기
        </button>
        <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => onClose(null)}>
          취소
        </button>
      </div>
    </div>
  );
}

function PresetEditor({
  preset,
  initialItems,
  onSave,
  onClose,
}: {
  preset: PresetOption;
  initialItems: PresetItem[];
  onSave: PresetHandlers['onUpdatePreset'];
  onClose: () => void;
}) {
  const [name, setName] = useState(preset.label);
  const [emoji, setEmoji] = useState(preset.emoji);
  const [items, setItems] = useState(initialItems);
  const [side, setSide] = useState(SIDES[0].value);
  const [kind, setKind] = useState(KINDS[0].value);
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  const pending = (): PresetItem[] => (value.trim() ? [{ key: `${side}_${kind}`, value: value.trim() }] : []);

  const add = () => {
    setItems((current) => [...current, ...pending()]);
    setValue('');
  };

  const save = async () => {
    // 입력칸에 남은 값도 포함 (말없이 사라지지 않게)
    const result = await onSave(preset.value, name, emoji, [...items, ...pending()]);
    if (result.error) setError(result.error);
    else onClose();
  };

  return (
    <div role="group" aria-label="프리셋 수정" style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
      <NameFields name={name} emoji={emoji} onName={setName} onEmoji={setEmoji} />
      <div style={row}>
        <select className="tm-select" aria-label="분류" value={side} onChange={(e) => setSide(e.target.value)}>
          {SIDES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <select className="tm-select" aria-label="규칙 유형" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>{k.label}</option>
          ))}
        </select>
      </div>
      <div style={{ ...row, flexWrap: 'nowrap' }}>
        <input
          className="tm-rule-input"
          aria-label="규칙 값"
          placeholder={KINDS.find((k) => k.value === kind)?.placeholder}
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.nativeEvent.isComposing) add();
          }}
          style={{ minWidth: 0 }}
        />
        <button className="tm-btn-small tm-btn-ghost" type="button" onClick={add} disabled={!value.trim()}>
          추가
        </button>
      </div>
      <div className="tm-preset-rules" style={{ maxHeight: 220, overflow: 'auto' }}>
        {items.length === 0 && <div className="tm-empty-row">아직 규칙이 없습니다.</div>}
        {items.map((item, index) => {
          const label = describeKey(item.key);
          return (
            <div
              key={`${item.key}:${item.value}:${index}`}
              style={{ ...row, flexWrap: 'nowrap', padding: '5px 0', borderTop: '1px solid var(--tm-line)' }}
            >
              <span style={{ ...muted, flex: 'none', width: 130 }}>{label.side} · {label.kind}</span>
              <span style={{ flex: 1, minWidth: 0, fontSize: 12, fontWeight: 700, color: 'var(--tm-ink)', wordBreak: 'break-all' }}>
                {item.value}
              </span>
              <button
                className="tm-btn-small tm-btn-ghost"
                type="button"
                aria-label={`${item.value} 빼기`}
                onClick={() => setItems((current) => current.filter((_, i) => i !== index))}
              >
                빼기
              </button>
            </div>
          );
        })}
      </div>
      {error && <div className="tm-rule-error" style={{ marginBottom: 0 }}>{error}</div>}
      <div style={row}>
        <button className="tm-btn-small tm-btn-primary" type="button" onClick={save}>
          프리셋 저장
        </button>
        <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onClose}>
          취소
        </button>
      </div>
    </div>
  );
}

export default function PresetSection({
  data,
  onSetProfile,
  onApplyPreset,
  onCreatePreset,
  onUpdatePreset,
  onDeletePreset,
}: PresetHandlers & { data: SettingsData }) {
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const selected = data.profileOptions.find((o) => o.value && o.value === data.profile);
  const editing = !!selected?.custom && editingId === selected.value;

  const select = (id: string) => {
    setEditingId(null);
    setConfirmDeleteId(null);
    onSetProfile(id);
  };

  return (
    <>
      <div className="tm-preset-grid">
        {data.profileOptions
          .filter((opt) => opt.value)
          .map((opt) => (
            <button
              key={opt.value}
              className={`tm-preset-item${data.profile === opt.value ? ' active' : ''}`}
              type="button"
              aria-pressed={data.profile === opt.value}
              title={opt.custom ? `${opt.label} (내 프리셋)` : opt.label}
              onClick={() => select(opt.value)}
            >
              <span className="tm-preset-emoji">{opt.emoji}</span>
              <span className="tm-preset-name" style={{ width: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {opt.label}
              </span>
            </button>
          ))}
        <button
          className="tm-preset-item"
          type="button"
          aria-expanded={creating}
          onClick={() => {
            setEditingId(null);
            setCreating((open) => !open);
          }}
        >
          <span className="tm-preset-emoji">＋</span>
          <span className="tm-preset-name">새 프리셋</span>
        </button>
      </div>

      {creating && (
        <CreateForm
          key={data.profile}
          selected={selected}
          onCreate={onCreatePreset}
          onClose={(created) => {
            setCreating(false);
            // 빈 프리셋은 규칙이 있어야 쓸모 있으므로 편집기를 바로 염
            if (created && created.presetItems.length === 0) setEditingId(created.profile);
          }}
        />
      )}

      {selected && editing && (
        <PresetEditor
          key={selected.value}
          preset={selected}
          initialItems={data.presetItems}
          onSave={onUpdatePreset}
          onClose={() => setEditingId(null)}
        />
      )}

      {selected && !editing && !creating && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ ...muted, marginBottom: 6 }}>
            {selected.label} · 후보 규칙 {data.presetItems.length}개
            {selected.custom ? ' · 내 프리셋' : ' · 기본 프리셋 (복제해서 바꿀 수 있어요)'}
          </div>
          <div style={row}>
            <button
              className="tm-btn-small tm-btn-primary"
              type="button"
              onClick={onApplyPreset}
              disabled={data.presetItems.length === 0}
            >
              선택 규칙 적용
            </button>
            {selected.custom ? (
              <>
                <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => setEditingId(selected.value)}>
                  수정
                </button>
                <button
                  className="tm-btn-small tm-btn-ghost"
                  type="button"
                  onClick={() => {
                    if (confirmDeleteId === selected.value) onDeletePreset(selected.value);
                    else setConfirmDeleteId(selected.value);
                  }}
                >
                  {confirmDeleteId === selected.value ? '정말 삭제' : '삭제'}
                </button>
              </>
            ) : (
              <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => setCreating(true)}>
                복제해서 만들기
              </button>
            )}
          </div>
          {confirmDeleteId === selected.value && (
            <div style={{ ...muted, marginTop: 4 }}>이미 적용한 규칙은 삭제되지 않아요.</div>
          )}
        </div>
      )}
    </>
  );
}
