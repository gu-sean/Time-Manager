import { useEffect, useState } from 'react';
import { dismissRuleSuggestion, getDismissedSuggestions, previewAiRequest, restoreRuleSuggestion } from '../api';
import { useAiRequest } from '../hooks/useAiRequest';
import { AiFailure, AiPreview, AiProgress } from './AiRequestControls';
import type { AIRuleSuggestion, AIRuleSuggestionsResult, RuleItem, RuleSuggestion, RulesData } from '../types';

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
  external: boolean;
  onGetAiSuggestions: (requestId: string, builtin: boolean) => Promise<AIRuleSuggestionsResult>;
}

interface EditTarget {
  key: string;
  value: string;
}

function RuleSuggestions({
  external,
  onGetSuggestions,
  onGetAiSuggestions,
  onApplySuggestion,
}: Pick<RulesProps, 'external' | 'onGetSuggestions' | 'onGetAiSuggestions' | 'onApplySuggestion'>) {
  const [suggestions, setSuggestions] = useState<RuleSuggestion[] | null>(null);
  const [recommendations, setRecommendations] = useState<Record<string, AIRuleSuggestion>>({});
  const [analysis, setAnalysis] = useState<{ source: string; skipped: number; excluded: number } | null>(null);
  const [hidden, setHidden] = useState<string[]>([]);
  const [showHidden, setShowHidden] = useState(false);
  const request = useAiRequest();
  const [error, setError] = useState('');
  const [offerBuiltin, setOfferBuiltin] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [applyingAll, setApplyingAll] = useState(false);
  const [applied, setApplied] = useState('');

  useEffect(() => {
    let cancelled = false;
    onGetSuggestions().then((result) => {
      if (!cancelled) setSuggestions(result);
    });
    getDismissedSuggestions().then((result) => {
      if (!cancelled) setHidden(result);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const recommend = async (builtin = false) => {
    setError('');
    setOfferBuiltin(false);
    // 이전 응답은 제거: 새 응답으로 착각하지 않게 함
    setRecommendations({});
    setAnalysis(null);
    setConfirmAll(false);
    setApplied('');
    try {
      const result = await request.run((requestId) => onGetAiSuggestions(requestId, builtin));
      if (!result) return;
      setRecommendations(Object.fromEntries(result.items.map((item) => [item.target, item])));
      setAnalysis(result.error ? null : { source: result.source, skipped: result.skipped, excluded: result.excluded });
      setError(result.error);
      setOfferBuiltin(result.canFallback);
    } catch {
      setError('분석 중 오류가 발생했어요.');
      setOfferBuiltin(external);
    }
  };

  const cancel = () => {
    if (!request.cancel()) return;
    setError('분석을 취소했어요.');
    setOfferBuiltin(external);
  };

  const removeRow = (target: string) => {
    setSuggestions((prev) => (prev ? prev.filter((s) => s.target !== target) : prev));
  };

  /** 계속 숨김. "중립으로 두기" 선택도 이 방식으로 기억. */
  const dismiss = async (target: string) => {
    setPending(target);
    try {
      setHidden(await dismissRuleSuggestion(target));
      removeRow(target);
    } finally {
      setPending(null);
    }
  };

  const unhide = async (target: string) => {
    setHidden(await restoreRuleSuggestion(target));
    setSuggestions(await onGetSuggestions());
  };

  const apply = async (target: string, category: string) => {
    setPending(target);
    try {
      const result = await onApplySuggestion(target, category);
      if (result.error) {
        setError(result.error);
        setOfferBuiltin(false);
      } else removeRow(target);
    } finally {
      setPending(null);
    }
  };

  // "중립"은 일괄 등록 제외: 중립 유지 = 추천 숨김이므로 하나씩 선택
  const recommendedRules = (suggestions ?? []).flatMap((s) => {
    const category = recommendations[s.target]?.category;
    return category === 'productive' || category === 'unproductive' ? [{ target: s.target, name: s.displayTarget, category }] : [];
  });

  const applyAll = async () => {
    setConfirmAll(false);
    setApplyingAll(true);
    setError('');
    const failed: string[] = [];
    let done = 0;
    try {
      // 하나씩 실행: 호출마다 규칙 파일을 다시 씀
      for (const rule of recommendedRules) {
        const result = await onApplySuggestion(rule.target, rule.category);
        if (result.error) failed.push(result.error);
        else {
          done += 1;
          removeRow(rule.target);
        }
      }
    } finally {
      setApplyingAll(false);
      setApplied(done ? `추천 ${done}개를 규칙으로 등록했어요.` : '');
      if (failed.length) setError(failed.join(' '));
    }
  };

  if (!suggestions) return null;

  return (
    <div className="tm-card">
      <div className="tm-rule-list-head" style={{ marginBottom: 6 }}>
        <div className="tm-card-title">분류 제안</div>
        <button
          className="tm-btn-small tm-btn-primary"
          type="button"
          onClick={() => recommend()}
          disabled={request.loading || suggestions.length === 0}
        >
          {request.loading ? '분석 중…' : analysis ? '다시 분석' : '✨ 맞춤 추천 받기'}
        </button>
      </div>
      <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginBottom: 10 }}>
        최근 자주 쓴 앱·사이트 중 아직 규칙이 없는 항목입니다. 분류를 선택하면 규칙으로 등록됩니다.{' '}
        {external ? '맞춤 추천을 받으면 앱 이름과 도메인이 선택한 AI 서버로 전송됩니다.' : '맞춤 추천은 이 PC에서만 분석합니다.'}
        {analysis && ` (${analysis.source})`}
      </div>
      {external && suggestions.length > 0 && <AiPreview load={() => previewAiRequest('suggestions')} />}
      {request.loading && <AiProgress elapsed={request.elapsed} external={external} onCancel={cancel} />}
      {error && <AiFailure message={error} onUseBuiltin={offerBuiltin ? () => recommend(true) : undefined} />}
      {suggestions.length === 0 && <div className="tm-empty-row">제안할 항목이 없습니다.</div>}
      {analysis && analysis.skipped > 0 && (
        <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginBottom: 4 }}>
          {analysis.skipped}개 항목은 판단할 근거가 부족해 추천하지 않았어요.
        </div>
      )}
      {analysis && analysis.excluded > 0 && (
        <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginBottom: 4 }}>
          {analysis.excluded}개 항목은 전송 제외 목록에 있어 보내지 않았어요.
        </div>
      )}
      {applied && (
        <div role="status" style={{ fontSize: 12, fontWeight: 700, color: 'var(--tm-ok)', marginBottom: 6 }}>
          {applied}
        </div>
      )}
      {recommendedRules.length > 1 && !confirmAll && (
        <button
          className="tm-btn-small tm-btn-ghost"
          type="button"
          style={{ marginBottom: 8 }}
          disabled={applyingAll || pending !== null}
          onClick={() => setConfirmAll(true)}
        >
          {applyingAll ? '등록 중…' : `추천대로 모두 등록 (${recommendedRules.length}개)`}
        </button>
      )}
      {confirmAll && (
        <div className="tm-rule-offer" style={{ marginTop: 0, marginBottom: 8 }}>
          <span>
            {recommendedRules.map((rule) => `${rule.name} → ${rule.category === 'productive' ? '생산적' : '비생산적'}`).join(', ')}
          </span>
          <span style={{ display: 'flex', gap: 6 }}>
            <button className="tm-btn-small tm-btn-primary" type="button" onClick={applyAll}>
              이대로 등록
            </button>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => setConfirmAll(false)}>
              취소
            </button>
          </span>
        </div>
      )}
      {suggestions.map((s) => {
        const recommended = recommendations[s.target];
        const buttonClass = (category: string) =>
          `tm-btn-small ${recommended?.category === category ? 'tm-btn-primary' : 'tm-btn-ghost'}`;
        return (
          <div
            key={s.target}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--tm-line)', flexWrap: 'wrap' }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--tm-ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {s.displayTarget} <span style={{ fontWeight: 500, color: 'var(--tm-muted)' }}>· {s.timeLabel}</span>
              </div>
              {recommended && (
                <div style={{ fontSize: 11, color: 'var(--tm-ink-4)' }}>
                  <b>{recommended.categoryLabel} 추천</b>
                  {recommended.reason && ` · ${recommended.reason}`}
                </div>
              )}
            </div>
            {(['productive', 'unproductive'] as const).map((category) => (
              <button
                key={category}
                className={buttonClass(category)}
                type="button"
                aria-label={`${s.displayTarget} ${category === 'productive' ? '생산적' : '비생산적'}으로 등록`}
                disabled={applyingAll || pending === s.target}
                onClick={() => apply(s.target, category)}
              >
                {category === 'productive' ? '생산적' : '비생산적'}
              </button>
            ))}
            <button
              className={buttonClass('neutral')}
              type="button"
              aria-label={`${s.displayTarget} 중립으로 두고 제안 숨기기`}
              disabled={applyingAll || pending === s.target}
              onClick={() => dismiss(s.target)}
            >
              {recommended?.category === 'neutral' ? '중립으로 두기' : '무시'}
            </button>
          </div>
        );
      })}
      {hidden.length > 0 && (
        <div style={{ marginTop: 8, borderTop: '1px solid var(--tm-line)', paddingTop: 8 }}>
          <button
            className="tm-btn-small tm-btn-ghost"
            type="button"
            aria-expanded={showHidden}
            onClick={() => setShowHidden((value) => !value)}
          >
            숨긴 항목 {hidden.length}개 {showHidden ? '닫기' : '보기'}
          </button>
          {showHidden &&
            hidden.map((name) => (
              <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0' }}>
                <span style={{ flex: 1, fontSize: 12, color: 'var(--tm-ink-3)' }}>{name}</span>
                <button className="tm-btn-small tm-btn-ghost" type="button" aria-label={`${name} 다시 제안받기`} onClick={() => unhide(name)}>
                  되돌리기
                </button>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

export default function Rules({
  data,
  onAdd,
  onUpdate,
  onDelete,
  onGetSuggestions,
  onApplySuggestion,
  external,
  onGetAiSuggestions,
}: RulesProps) {
  const [ruleType, setRuleType] = useState(TYPE_OPTIONS[0]);
  const [category, setCategory] = useState(CATEGORY_OPTIONS[0]);
  const [value, setValue] = useState('');
  const [editing, setEditing] = useState<EditTarget | null>(null);
  const [page, setPage] = useState(0);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

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
      <RuleSuggestions
        external={external}
        onGetSuggestions={onGetSuggestions}
        onGetAiSuggestions={onGetAiSuggestions}
        onApplySuggestion={onApplySuggestion}
      />

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
          <span style={{ fontSize: 11, color: 'var(--tm-muted)' }}>전체 {data.total}개</span>
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
              <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--tm-muted)' }} aria-hidden="true">{rule.priority}</span>
              <span className="tm-rule-row-type">{rule.ruleType}</span>
              <span className="tm-rule-row-value">{rule.value}</span>
              <span className="tm-cat-pill" style={{ background: bg, color: fg }}>
                {rule.category}
              </span>
              <button
                className={`tm-rule-row-delete${confirmDelete === `${rule.key}:${rule.value}` ? ' confirming' : ''}`}
                type="button"
                aria-label={
                  confirmDelete === `${rule.key}:${rule.value}` ? `${rule.value} 규칙 삭제 확인` : `${rule.value} 규칙 삭제`
                }
                title="삭제"
                onBlur={() => setConfirmDelete(null)}
                onKeyDown={(e) => {
                  e.stopPropagation(); // 행도 Enter·Space 에 반응함
                  if (e.key === 'Escape') setConfirmDelete(null);
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  const id = `${rule.key}:${rule.value}`;
                  if (confirmDelete !== id) {
                    setConfirmDelete(id);
                    e.currentTarget.focus(); // 다른 곳을 누르면 취소되도록 포커스
                    return;
                  }
                  setConfirmDelete(null);
                  if (isEditing) resetForm();
                  onDelete(rule.key, rule.value);
                }}
              >
                {confirmDelete === `${rule.key}:${rule.value}` ? '삭제?' : <span aria-hidden="true">🗑</span>}
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
        <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginTop: 11 }}>
          규칙을 클릭하면 위 편집기에서 수정할 수 있습니다. 우선순위가 높은 규칙이 먼저 적용됩니다.
        </div>
      </div>
    </div>
  );
}
