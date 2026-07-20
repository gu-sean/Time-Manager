import { useEffect, useState } from 'react';
import type { RuleItem, RuleSuggestion, RulesData } from '../types';

const PAGE_SIZE = 20;
const TYPE_OPTIONS = ['도메인', '앱 이름', '창 제목 키워드'];
const CATEGORY_OPTIONS = ['생산적', '비생산적', '중립', '기록 제외'];

const CATEGORY_COLORS: Record<string, [string, string]> = {
  생산적: ['#EAF1EC', '#6F9A7C'],
  비생산적: ['#F8EDE3', '#CB8056'],
  중립: ['#EBF0F4', '#7E97AC'],
  '기록 제외': ['#F0EAE2', '#A98A6F'],
};

interface RulesProps {
  data: RulesData;
  onAdd: (ruleType: string, category: string, value: string) => void;
  onUpdate: (oldKey: string, oldValue: string, ruleType: string, category: string, value: string) => void;
  onDelete: (key: string, value: string) => void;
  onGetSuggestions: () => Promise<RuleSuggestion[]>;
  onApplySuggestion: (target: string, category: string) => Promise<RulesData>;
}

interface EditTarget {
  key: string;
  value: string;
}

function RuleSuggestions({ onGetSuggestions, onApplySuggestion }: Pick<RulesProps, 'onGetSuggestions' | 'onApplySuggestion'>) {
  const [suggestions, setSuggestions] = useState<RuleSuggestion[] | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    onGetSuggestions().then((result) => {
      if (!cancelled) setSuggestions(result);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const dismiss = (target: string) => {
    setSuggestions((prev) => (prev ? prev.filter((s) => s.target !== target) : prev));
  };

  const apply = async (target: string, category: string) => {
    setPending(target);
    await onApplySuggestion(target, category);
    setPending(null);
    dismiss(target);
  };

  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="tm-card">
      <div className="tm-card-title" style={{ marginBottom: 6 }}>
        분류 제안
      </div>
      <div style={{ fontSize: 11, color: '#A79F92', marginBottom: 10 }}>
        최근 자주 등장했지만 아직 규칙이 없는 활동입니다. 분류를 선택하면 규칙으로 등록됩니다.
      </div>
      {suggestions.map((s) => (
        <div
          key={s.target}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid #F0ECE3', flexWrap: 'wrap' }}
        >
          <span style={{ flex: 1, minWidth: 0, fontSize: 12, fontWeight: 700, color: '#3B362E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {s.displayTarget}
          </span>
          <span style={{ fontSize: 11, color: '#A79F92' }}>{s.timeLabel}</span>
          <button
            className="tm-btn-small tm-btn-primary"
            type="button"
            disabled={pending === s.target}
            onClick={() => apply(s.target, 'productive')}
          >
            생산적
          </button>
          <button
            className="tm-btn-small tm-btn-ghost"
            type="button"
            disabled={pending === s.target}
            onClick={() => apply(s.target, 'unproductive')}
          >
            비생산적
          </button>
          <button
            className="tm-btn-small tm-btn-ghost"
            type="button"
            aria-label={`${s.displayTarget} 제안 무시`}
            disabled={pending === s.target}
            onClick={() => dismiss(s.target)}
          >
            무시
          </button>
        </div>
      ))}
    </div>
  );
}

export default function Rules({ data, onAdd, onUpdate, onDelete, onGetSuggestions, onApplySuggestion }: RulesProps) {
  const [ruleType, setRuleType] = useState(TYPE_OPTIONS[0]);
  const [category, setCategory] = useState(CATEGORY_OPTIONS[0]);
  const [value, setValue] = useState('');
  const [editing, setEditing] = useState<EditTarget | null>(null);
  const [page, setPage] = useState(0);

  const pageCount = Math.max(1, Math.ceil(data.items.length / PAGE_SIZE));

  useEffect(() => {
    if (page > pageCount - 1) setPage(pageCount - 1);
  }, [page, pageCount]);

  const currentPage = Math.min(page, pageCount - 1);
  const pageItems = data.items.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  const resetForm = () => {
    setEditing(null);
    setRuleType(TYPE_OPTIONS[0]);
    setCategory(CATEGORY_OPTIONS[0]);
    setValue('');
  };

  const startEdit = (rule: RuleItem) => {
    setEditing({ key: rule.key, value: rule.value });
    setRuleType(rule.ruleType);
    setCategory(rule.category);
    setValue(rule.value);
  };

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    if (editing) {
      onUpdate(editing.key, editing.value, ruleType, category, trimmed);
    } else {
      onAdd(ruleType, category, trimmed);
    }
    resetForm();
  };

  return (
    <div className="tm-page">
      <RuleSuggestions onGetSuggestions={onGetSuggestions} onApplySuggestion={onApplySuggestion} />

      <div className="tm-card">
        <div className="tm-card-title" style={{ marginBottom: 13 }}>
          {editing ? '규칙 수정' : '규칙 편집기'}
        </div>
        <div className="tm-rule-form">
          <label className="tm-visually-hidden" htmlFor="rule-type">규칙 유형</label>
          <select id="rule-type" className="tm-select" value={ruleType} onChange={(e) => setRuleType(e.target.value)}>
            {TYPE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          <label className="tm-visually-hidden" htmlFor="rule-category">분류</label>
          <select id="rule-category" className="tm-select" value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          <input
            id="rule-value"
            className="tm-rule-input"
            placeholder="값 입력 (예: github.com)"
            aria-label="규칙 값"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submit();
              if (e.key === 'Escape' && editing) resetForm();
            }}
          />
          <button className="tm-btn-small tm-btn-primary" type="button" onClick={submit}>
            {editing ? '저장' : '+ 추가'}
          </button>
          {editing && (
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={resetForm}>
              취소
            </button>
          )}
        </div>
        {editing && (
          <div className="tm-rule-edit-hint">
            '{editing.value}' 규칙을 수정하는 중입니다. 값을 바꾸고 저장하세요.
          </div>
        )}
        {data.error && <div className="tm-rule-error">{data.error}</div>}
      </div>

      <div className="tm-card">
        <div className="tm-rule-list-head">
          <div className="tm-card-title">등록된 규칙 목록</div>
          <span style={{ fontSize: 11, color: '#A79F92' }}>전체 {data.total}개</span>
        </div>
        {data.items.length === 0 && <div className="tm-empty-row">등록된 규칙이 없습니다.</div>}
        {pageItems.map((rule) => {
          const [bg, fg] = CATEGORY_COLORS[rule.category] ?? CATEGORY_COLORS['중립'];
          const isEditing = editing?.key === rule.key && editing?.value === rule.value;
          return (
            <div
              className={`tm-rule-row tm-rule-row-clickable${isEditing ? ' editing' : ''}`}
              key={`${rule.key}:${rule.value}`}
              role="button"
              tabIndex={0}
              aria-label={`${rule.value} 규칙 수정`}
              aria-pressed={isEditing}
              onClick={() => startEdit(rule)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startEdit(rule); } }}
            >
              <span style={{ fontSize: 12, fontWeight: 800, color: '#C0B8A9' }} aria-hidden="true">{rule.priority}</span>
              <span className="tm-rule-row-type">{rule.ruleType}</span>
              <span className="tm-rule-row-value">{rule.value}</span>
              <span className="tm-cat-pill" style={{ background: bg, color: fg }}>
                {rule.category}
              </span>
              <button
                className="tm-rule-row-delete"
                type="button"
                aria-label={`${rule.value} 규칙 삭제`}
                onClick={(e) => {
                  e.stopPropagation();
                  if (isEditing) resetForm();
                  onDelete(rule.key, rule.value);
                }}
              >
                <span aria-hidden="true">🗑</span>
              </button>
            </div>
          );
        })}
        {pageCount > 1 && (
          <div className="tm-pagination">
            <button
              className="tm-page-btn"
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
            >
              ‹ 이전
            </button>
            <span className="tm-page-status">
              {currentPage + 1} / {pageCount} 페이지
            </span>
            <button
              className="tm-page-btn"
              type="button"
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              disabled={currentPage === pageCount - 1}
            >
              다음 ›
            </button>
          </div>
        )}
        <div style={{ fontSize: 11, color: '#A79F92', marginTop: 11 }}>
          규칙을 클릭하면 위 편집기에서 수정할 수 있습니다. 우선순위가 높은 규칙이 먼저 적용됩니다.
        </div>
      </div>
    </div>
  );
}
