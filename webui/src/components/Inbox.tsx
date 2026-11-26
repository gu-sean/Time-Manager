import { useEffect, useState } from 'react';
import type { InboxData } from '../types';

const PAGE_SIZE = 20;

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
}

export default function Inbox({ data, onSearch, onClearSearch, onDelete, onRestore, onReclassify }: InboxProps) {
  const [query, setQuery] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [reclassifying, setReclassifying] = useState(false);
  // Looked up from the latest data so it never shows a stale category or a removed record.
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

  const pageCount = Math.max(1, Math.ceil(data.records.length / PAGE_SIZE));

  useEffect(() => {
    if (page > pageCount - 1) setPage(pageCount - 1);
  }, [page, pageCount]);

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
          <div className="tm-card-title">활동 기록</div>
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

        {data.searchActive && data.resultCount !== null && (
          <div role="status" aria-live="polite" style={{ fontSize: 11.5, color: 'var(--tm-ink-4)', marginBottom: 8 }}>
            최근 30일 · 검색 결과 {data.resultCount}건
          </div>
        )}

        <div className="tm-table-head" style={{ gridTemplateColumns: '130px 90px 1fr 90px' }}>
          <span>시간</span>
          <span>분류</span>
          <span>활동</span>
          <span>사용 시간</span>
        </div>
        {data.records.length === 0 && <div className="tm-empty-row">기록된 데이터가 없습니다.</div>}
        {pageRecords.map((row) => (
          <div
            key={row.id}
            className={`tm-table-row${selected?.id === row.id ? ' selected' : ''}`}
            style={{ gridTemplateColumns: '130px 90px 1fr 90px' }}
            role="button"
            tabIndex={0}
            aria-label={`${row.time} ${row.label} ${row.duration} 선택`}
            aria-pressed={selected?.id === row.id}
            onClick={() => setSelectedId(row.id)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelectedId(row.id); } }}
          >
            <span style={{ color: 'var(--tm-ink-3)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{row.time}</span>
            <span>
              <CategoryPill category={row.category} label={row.categoryLabel} />
            </span>
            <span style={{ color: 'var(--tm-ink)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {row.label}
            </span>
            <span style={{ color: 'var(--tm-ink-2)', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{row.duration}</span>
          </div>
        ))}

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

        <div className="tm-editor-actions" role="group" aria-label="선택 기록 분류 변경">
          <span style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--tm-ink-4)', alignSelf: 'center' }}>선택 기록 분류</span>
          {CATEGORY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`tm-btn-small ${selected?.category === opt.value ? 'tm-btn-primary' : 'tm-btn-ghost'}`}
              type="button"
              aria-pressed={selected?.category === opt.value}
              disabled={!selected || reclassifying || selected.category === opt.value}
              onClick={() => reclassify(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="tm-editor-actions">
          <button
            className="tm-btn-small tm-btn-ghost"
            type="button"
            disabled={!selected}
            onClick={() => selected && onDelete(selected.id)}
          >
            선택 기록 삭제
          </button>
          <button className="tm-btn-small tm-btn-ghost" type="button" onClick={onRestore}>
            최근 삭제 복원
          </button>
        </div>
        <div style={{ fontSize: 11, color: '#A79F92', marginTop: 11 }}>
          기록을 선택해 분류를 바꾸면 그 기록에만 적용되고, 내장 분류 추천이 학습에 우선 반영해요. 앞으로의 활동에도
          적용하려면 규칙 탭에서 규칙을 추가하세요.
        </div>
      </div>
    </div>
  );
}
