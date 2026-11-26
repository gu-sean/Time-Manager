import { Fragment, useState } from 'react';
import { previewDeleteTarget } from '../api';
import type { DeletePreview, InboxData, ManualEntry } from '../types';

const PAGE_SIZE = 20;
// 고정 열은 좁게: 남는 폭은 활동 이름에 배정
const INBOX_COLUMNS = '96px 78px minmax(0, 1fr) 72px';

const CATEGORY_COLORS: Record<string, [string, string]> = {
  productive: ['#EAF1EC', '#6F9A7C'],
  unproductive: ['#F8EDE3', '#CB8056'],
  neutral: ['#EBF0F4', '#7E97AC'],
};

const CATEGORY_OPTIONS = [
  { value: 'productive', label: '생산적' },
  { value: 'unproductive', label: '비생산적' },
  { value: 'neutral', label: '중립' },
];

function CategoryPill({ category, label }: { category: string; label: string }) {
  const [bg, fg] = CATEGORY_COLORS[category] ?? CATEGORY_COLORS.neutral;
  return (
    <span className="tm-cat-pill" style={{ background: bg, color: fg }}>
      {label}
    </span>
  );
}

interface InboxProps {
  data: InboxData;
  onSearch: (query: string, category: string | null) => void;
  onClearSearch: () => void;
  onDelete: (eventId: number) => void;
  onRestore: () => void;
  onReclassify: (eventId: number, category: string) => Promise<void>;
  onAddRule: (eventId: number) => Promise<void>;
  onDeleteTarget: (eventId: number) => Promise<void>;
  onAddManual: (entry: ManualEntry) => Promise<string>;
}

const EMPTY_ENTRY: ManualEntry = { start: '09:00', minutes: 30, label: '', category: 'productive' };

/** PC 밖에서 한 일 (회의, 종이 독서 등)을 직접 추가. */
function ManualEntryForm({ onAdd, onClose }: { onAdd: (entry: ManualEntry) => Promise<string>; onClose: () => void }) {
  const [entry, setEntry] = useState<ManualEntry>(EMPTY_ENTRY);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      const problem = await onAdd(entry);
      setError(problem);
      if (!problem) onClose();
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="tm-manual-form" role="group" aria-label="기록 직접 추가">
      <div className="tm-manual-fields">
        <label>
          <span>시작</span>
          <input className="tm-select" type="time" value={entry.start} onChange={(e) => setEntry({ ...entry, start: e.target.value })} />
        </label>
        <label>
          <span>시간(분)</span>
          <input
            className="tm-select"
            type="number"
            min={1}
            max={720}
            value={entry.minutes}
            onChange={(e) => setEntry({ ...entry, minutes: e.target.value === '' ? '' : Number(e.target.value) })}
          />
        </label>
        <label className="tm-manual-label">
          <span>한 일</span>
          <input
            className="tm-rule-input"
            maxLength={80}
            placeholder="예: 팀 회의, 책 읽기"
            value={entry.label}
            onChange={(e) => setEntry({ ...entry, label: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.nativeEvent.isComposing) void submit();
            }}
          />
        </label>
        <label>
          <span>분류</span>
          <select className="tm-select" value={entry.category} onChange={(e) => setEntry({ ...entry, category: e.target.value })}>
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </label>
      </div>
      {error && <div className="tm-rule-error" role="alert" style={{ margin: '8px 0 0' }}>{error}</div>}
      <div className="tm-manual-actions">
        <span className="tm-note">위에서 고른 날짜에 추가돼요. 기록된 시간과 겹치면 추가하지 않아요.</span>
        <button className="tm-btn-small tm-btn-primary" type="button" disabled={busy} onClick={submit}>
          추가
        </button>
        <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onClose}>
          취소
        </button>
      </div>
    </div>
  );
}

export default function Inbox({
  data, onSearch, onClearSearch, onDelete, onRestore, onReclassify, onAddRule, onDeleteTarget, onAddManual,
}: InboxProps) {
  const [adding, setAdding] = useState(false);
  // "이 사이트 기록 모두 삭제": 지울 건수를 먼저 보여 주고 한 번 더 확인
  const [deleteAll, setDeleteAll] = useState<{ id: number; preview: DeletePreview } | null>(null);
  const askDeleteAll = async (eventId: number) => setDeleteAll({ id: eventId, preview: await previewDeleteTarget(eventId) });
  const confirmDeleteAll = async () => {
    if (!deleteAll) return;
    setDeleteAll(null);
    setSelectedId(null);
    await onDeleteTarget(deleteAll.id);
  };
  const [query, setQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [reclassifying, setReclassifying] = useState(false);
  // 최신 데이터에서 조회: 바뀐 분류나 삭제된 기록이 남지 않음
  const selected = data.records.find((record) => record.id === selectedId) ?? null;

  const reclassify = async (category: string) => {
    if (!selected) return;
    setReclassifying(true);
    try {
      await onReclassify(selected.id, category);
    } finally {
      setReclassifying(false);
    }
  };
  const [page, setPage] = useState(0);

  const addRule = async () => {
    if (!selected) return;
    setReclassifying(true);
    try {
      await onAddRule(selected.id);
    } finally {
      setReclassifying(false);
    }
  };

  const pageCount = Math.max(1, Math.ceil(data.records.length / PAGE_SIZE));

  const currentPage = Math.min(page, pageCount - 1);
  const pageRecords = data.records.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);

  const submitSearch = () => {
    setPage(0);
    if (!query.trim() && !filterCategory) {
      onClearSearch();
      return;
    }
    onSearch(query.trim(), filterCategory || null);
  };

  const clearAll = () => {
    setQuery('');
    setFilterCategory('');
    setPage(0);
    onClearSearch();
  };

  return (
    <div className="tm-page">
      <div className="tm-card">
        <div className="tm-inbox-card-head">
          <div className="tm-inbox-title">
            <div className="tm-card-title">활동 기록</div>
            <button className="tm-btn-small tm-btn-ghost" type="button" aria-expanded={adding} onClick={() => setAdding((open) => !open)}>
              + 직접 추가
            </button>
          </div>
          <div className="tm-search-bar">
            <div className="tm-search-input-wrap">
              <span aria-hidden="true">🔍</span>
              <input
                className="tm-search-input"
                placeholder="활동 검색"
                aria-label="활동 검색"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submitSearch()}
              />
            </div>
            <label className="tm-visually-hidden" htmlFor="inbox-category-filter">분류 필터</label>
            <select id="inbox-category-filter" className="tm-select" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
              <option value="">전체</option>
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button className="tm-btn-small tm-btn-primary" type="button" onClick={submitSearch}>
              검색
            </button>
            <button className="tm-btn-small tm-btn-ghost" type="button" onClick={clearAll}>
              초기화
            </button>
          </div>
        </div>

        {adding && <ManualEntryForm onAdd={onAddManual} onClose={() => setAdding(false)} />}

        {data.searchActive && data.resultCount !== null && (
          <div role="status" aria-live="polite" style={{ fontSize: 11.5, color: 'var(--tm-ink-4)', marginBottom: 8 }}>
            최근 30일 · 검색 결과 {data.resultCount}건
            {data.truncated && ' (최신 결과만 표시해요. 검색어를 더 넣으면 좁혀져요.)'}
          </div>
        )}

        <div className="tm-table-head" style={{ gridTemplateColumns: INBOX_COLUMNS, columnGap: 10 }}>
          <span>시간</span>
          <span>분류</span>
          <span>활동</span>
          <span>사용 시간</span>
        </div>
        {data.records.length === 0 && <div className="tm-empty-row">기록된 데이터가 없습니다.</div>}
        {pageRecords.map((row) => (
          <Fragment key={row.id}>
          <div
            className={`tm-table-row${selected?.id === row.id ? ' selected' : ''}`}
            style={{ gridTemplateColumns: INBOX_COLUMNS, columnGap: 10 }}
            role="button"
            tabIndex={0}
            aria-label={`${row.time} ${row.label} ${row.duration} 선택`}
            aria-pressed={selected?.id === row.id}
            aria-expanded={selected?.id === row.id}
            onClick={() => setSelectedId(selected?.id === row.id ? null : row.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setSelectedId(selected?.id === row.id ? null : row.id);
              }
            }}
          >
            <span style={{ color: 'var(--tm-ink-3)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{row.time}</span>
            <span>
              <CategoryPill category={row.category} label={row.categoryLabel} />
            </span>
            <span style={{ minWidth: 0 }}>
              <span className="tm-ellipsis" style={{ color: 'var(--tm-ink)', fontWeight: 600 }} title={row.label}>
                {row.label}
              </span>
              {row.detail && (
                <span className="tm-ellipsis tm-subline" title={row.detail}>
                  {row.detail}
                </span>
              )}
            </span>
            <span style={{ color: 'var(--tm-ink-2)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{row.duration}</span>
          </div>
          {selected?.id === row.id && (
            <div className="tm-row-actions" role="group" aria-label={`${row.label} 기록 작업`}>
              <div className="tm-row-actions-line">
                <span className="tm-row-actions-label">분류 바꾸기</span>
                {CATEGORY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    className={`tm-btn-small ${row.category === opt.value ? 'tm-btn-primary' : 'tm-btn-ghost'}`}
                    type="button"
                    aria-pressed={row.category === opt.value}
                    disabled={reclassifying || row.category === opt.value}
                    onClick={() => reclassify(opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
                <span className="tm-row-actions-spacer" />
                <button className="tm-btn-small tm-btn-ghost tm-btn-danger-text" type="button" onClick={() => onDelete(row.id)}>
                  삭제
                </button>
                <button className="tm-btn-small tm-btn-ghost tm-btn-danger-text" type="button" onClick={() => askDeleteAll(row.id)}>
                  모두 삭제…
                </button>
                <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => setSelectedId(null)}>
                  닫기
                </button>
              </div>
              {deleteAll?.id === row.id && (
                <div className="tm-rule-offer tm-danger-offer" role="alert">
                  {deleteAll.preview.error ? (
                    <span>{deleteAll.preview.error}</span>
                  ) : (
                    <span>
                      <b>{deleteAll.preview.target}</b> {deleteAll.preview.kindLabel}의 기록 {deleteAll.preview.count}건(
                      {deleteAll.preview.timeLabel})을 모든 날짜에서 완전히 지울까요? 되돌릴 수 없어요.
                    </span>
                  )}
                  <span style={{ display: 'flex', gap: 6 }}>
                    {!deleteAll.preview.error && (
                      <button className="tm-btn-small tm-btn-danger" type="button" onClick={confirmDeleteAll}>
                        완전히 삭제
                      </button>
                    )}
                    <button className="tm-btn-small tm-btn-ghost" type="button" onClick={() => setDeleteAll(null)}>
                      취소
                    </button>
                  </span>
                </div>
              )}
              {row.ruleTarget && (
                <div className="tm-rule-offer">
                  <span>지금 규칙으로는 다음에 다르게 분류돼요.</span>
                  <button className="tm-btn-small tm-btn-primary" type="button" disabled={reclassifying} onClick={addRule}>
                    앞으로 {row.ruleTarget}도 {row.categoryLabel}으로 분류
                  </button>
                </div>
              )}
            </div>
          )}
          </Fragment>
        ))}

        {pageCount > 1 && (
          <div className="tm-pagination">
            <button
              className="tm-page-btn"
              type="button"
              onClick={() => setPage(Math.max(0, currentPage - 1))}
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
              onClick={() => setPage(Math.min(pageCount - 1, currentPage + 1))}
              disabled={currentPage === pageCount - 1}
            >
              다음 ›
            </button>
          </div>
        )}

        <div className="tm-editor-actions">
          <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onRestore}>
            최근 삭제 복원
          </button>
        </div>
        <div className="tm-note" style={{ marginTop: 11 }}>
          기록을 누르면 바로 아래에서 분류를 바꾸거나 삭제할 수 있어요. 바꾼 분류는 그 기록에만 적용되고, 내장 분류 추천이
          학습에 우선 반영해요. 삭제한 기록은 24시간 동안 되돌릴 수 있고, 그 뒤에는 파일에서도 지워져요(백업에는 들어가지
          않아요).
        </div>
      </div>
    </div>
  );
}
