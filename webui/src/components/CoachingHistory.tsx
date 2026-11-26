import { useState } from 'react';
import { clearCoachingHistory, deleteCoachingHistory, getCoachingHistory } from '../api';
import type { CoachingHistoryEntry } from '../types';

const muted = { fontSize: 11, color: 'var(--tm-muted)' } as const;

function periodLabel(entry: CoachingHistoryEntry) {
  return entry.scope === 'week' ? `${entry.startDay} ~ ${entry.endDay}` : entry.endDay;
}

/** 저장된 코칭 기록. 열람해도 전송 없음. */
export default function CoachingHistory() {
  const [entries, setEntries] = useState<CoachingHistoryEntry[] | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [error, setError] = useState('');

  const update = async (action: () => Promise<CoachingHistoryEntry[]>) => {
    setError('');
    setConfirmClear(false);
    try {
      setEntries(await action());
    } catch {
      setError('지난 코칭을 불러오지 못했어요.');
    }
  };

  const toggle = () => {
    if (entries) setEntries(null);
    else void update(getCoachingHistory);
  };

  return (
    <div style={{ marginTop: 10, borderTop: '1px solid var(--tm-line)', paddingTop: 8 }}>
      <button className="tm-btn-small tm-btn-ghost" type="button" aria-expanded={!!entries} onClick={toggle}>
        {entries ? '지난 코칭 닫기' : '지난 코칭 보기'}
      </button>
      {error && <div className="tm-rule-error" style={{ marginTop: 6 }}>{error}</div>}
      {entries && entries.length === 0 && <div className="tm-empty-row">저장된 코칭이 없습니다.</div>}
      {entries && entries.length > 0 && (
        <>
          {entries.map((entry) => (
            <div key={entry.id} style={{ borderBottom: '1px solid var(--tm-line)', padding: '8px 0' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  type="button"
                  aria-expanded={openId === entry.id}
                  onClick={() => setOpenId(openId === entry.id ? null : entry.id)}
                  style={{ flex: 1, minWidth: 0, textAlign: 'left', background: 'none', border: 0, padding: 0, cursor: 'pointer', fontFamily: 'inherit' }}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--tm-ink)' }}>{entry.headline}</div>
                  <div style={muted}>
                    {periodLabel(entry)} · {entry.source}
                  </div>
                </button>
                <button
                  className="tm-btn-small tm-btn-ghost"
                  type="button"
                  aria-label={`${periodLabel(entry)} ${entry.source} 코칭 삭제`}
                  onClick={() => update(() => deleteCoachingHistory(entry.id))}
                >
                  삭제
                </button>
              </div>
              {openId === entry.id && (
                <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12, lineHeight: 1.6, color: 'var(--tm-ink-2)' }}>
                  {[...entry.insights, ...entry.actions].map((line, index) => (
                    <li key={index}>{line}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
            <button
              className="tm-btn-small tm-btn-ghost"
              type="button"
              onClick={() => (confirmClear ? void update(clearCoachingHistory) : setConfirmClear(true))}
            >
              {confirmClear ? '정말 모두 삭제' : '모두 삭제'}
            </button>
            <span style={muted}>기간과 분석 방식마다 가장 최근 것 하나를 이 PC에 저장해요.</span>
          </div>
        </>
      )}
    </div>
  );
}
