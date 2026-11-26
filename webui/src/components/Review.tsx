import { useState } from 'react';
import { previewAiRequest } from '../api';
import { useAiRequest } from '../hooks/useAiRequest';
import { AiFailure, AiPreview, AiProgress } from './AiRequestControls';
import CoachingHistory from './CoachingHistory';
import type { AICoaching, ReviewData, ReviewStatGroup } from '../types';

function StatGroupCard({
  title,
  tag,
  tBg,
  tFg,
  group,
}: {
  title: string;
  tag: string;
  tBg: string;
  tFg: string;
  group: ReviewStatGroup;
}) {
  return (
    <div className="tm-card tm-review-stat-card">
      <span className="tm-review-tag" style={{ background: tBg, color: tFg }}>
        {tag}
      </span>
      <div className="tm-review-card-title">{title}</div>
      {group.empty ? (
        <div className="tm-empty-row">{group.note || '기록된 데이터가 없습니다.'}</div>
      ) : (
        <>
          <div className="tm-review-stat-grid">
            {group.stats.map((stat) => (
              <div className="tm-review-stat" key={stat.label}>
                <div className="tm-review-stat-value">
                  {stat.value}
                  {stat.unit && <span className="tm-review-stat-unit">{stat.unit}</span>}
                </div>
                <div className="tm-review-stat-label">{stat.label}</div>
              </div>
            ))}
          </div>
          {group.note && <div className="tm-review-stat-note">{group.note}</div>}
        </>
      )}
    </div>
  );
}

type CoachingScope = 'day' | 'week';

interface AiCoachingCardProps {
  external: boolean;
  dateIso: string;
  onGetCoaching: (
    scope: CoachingScope, dateIso: string, refresh: boolean, requestId: string, builtin: boolean,
  ) => Promise<AICoaching>;
}

function AiCoachingCard({ external, dateIso, onGetCoaching }: AiCoachingCardProps) {
  const [scope, setScope] = useState<CoachingScope>('day');
  const [result, setResult] = useState<AICoaching | null>(null);
  const request = useAiRequest();
  const loading = request.loading;
  const [notice, setNotice] = useState<{ message: string; offerBuiltin: boolean } | null>(null);

  const changeScope = (next: CoachingScope) => {
    request.cancel(); // 다른 범위의 응답이 여기에 표시되면 안 됨
    setScope(next);
    setResult(null);
    setNotice(null);
  };

  const run = async (refresh: boolean, builtin = false) => {
    setNotice(null);
    setResult(null);
    try {
      const next = await request.run((requestId) => onGetCoaching(scope, dateIso, refresh, requestId, builtin));
      if (!next) return;
      if (next.error) setNotice({ message: next.error, offerBuiltin: next.canFallback });
      else setResult(next);
    } catch {
      setNotice({ message: '분석 중 오류가 발생했어요.', offerBuiltin: external });
    }
  };

  const cancel = () => {
    if (request.cancel()) setNotice({ message: '분석을 취소했어요.', offerBuiltin: external });
  };

  return (
    <div className="tm-card">
      <div className="tm-rule-list-head" style={{ marginBottom: 6 }}>
        <div className="tm-card-title">✨ 맞춤 코칭</div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <div className="tm-segment" role="group" aria-label="코칭 범위">
            {(['day', 'week'] as const).map((value) => (
              <button key={value} type="button" aria-pressed={scope === value} onClick={() => changeScope(value)}>
                {value === 'day' ? '선택한 날' : '최근 7일'}
              </button>
            ))}
          </div>
          <button className="tm-btn-small tm-btn-primary" type="button" disabled={loading} onClick={() => run(!!result)}>
            {loading ? '분석 중…' : result ? '다시 분석' : '코칭 받기'}
          </button>
        </div>
      </div>
      {!result && !loading && !notice && (
        <div style={{ fontSize: 11, color: 'var(--tm-muted)' }}>
          {external
            ? '선택한 AI 서버로 집계된 시간 통계와 앱·도메인 이름만 전송해 코칭을 만들어요.'
            : '이 PC의 기록 통계로 코칭을 만들어요. 아무것도 전송하지 않습니다.'}
        </div>
      )}
      {external && (
        <div style={{ marginTop: 8 }}>
          <AiPreview key={scope} load={() => previewAiRequest('coaching', scope, dateIso)} />
        </div>
      )}
      {loading && <AiProgress elapsed={request.elapsed} external={external} onCancel={cancel} />}
      {notice && (
        <AiFailure message={notice.message} onUseBuiltin={notice.offerBuiltin ? () => run(false, true) : undefined} />
      )}
      {result && (
        <div>
          <div className="tm-review-suggestion-text" style={{ marginBottom: 8 }}>{result.headline}</div>
          {result.insights.length > 0 && (
            <ul style={{ margin: '0 0 8px', paddingLeft: 18, fontSize: 12.5, lineHeight: 1.6 }}>
              {result.insights.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          {result.actions.length > 0 && (
            <>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--tm-gold)', marginBottom: 2 }}>이렇게 해보세요</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, lineHeight: 1.6 }}>
                {result.actions.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </>
          )}
          <div style={{ fontSize: 11, color: 'var(--tm-muted)', marginTop: 8 }}>
            {result.scopeLabel} 기준 · {result.source}
            {result.reused && ' · 저장된 결과 (다시 전송하지 않음)'}
            {result.generated && ' · AI가 생성한 요약이라 부정확할 수 있어요.'}
          </div>
        </div>
      )}
      {/* 분석마다 다시 마운트: 열린 목록에 지난 항목이 남지 않음 */}
      <CoachingHistory key={result?.savedAt ?? 'none'} />
    </div>
  );
}

interface ReviewProps {
  data: ReviewData;
  external: boolean;
  dateIso: string;
  onGetCoaching: AiCoachingCardProps['onGetCoaching'];
}

export default function Review({ data, external, dateIso, onGetCoaching }: ReviewProps) {
  const { composition, highlights, suggestion, flow, focus } = data;
  return (
    <div className="tm-page">
      <div className="tm-card">
        <div className="tm-composition-head">
          <div className="tm-card-title">하루 구성</div>
          <div className="tm-composition-meta">총 {composition.total}</div>
        </div>
        {composition.segments.length === 0 ? (
          <div className="tm-empty-row">기록된 데이터가 없습니다.</div>
        ) : (
          <>
            <div className="tm-composition-bar">
              {composition.segments.map((seg) => (
                <div
                  className="tm-composition-seg"
                  key={seg.category}
                  style={{ width: `${seg.pct}%`, background: seg.color }}
                >
                  {seg.pct}%
                </div>
              ))}
            </div>
            <div className="tm-composition-legend">
              {composition.segments.map((seg) => (
                <span className="tm-composition-legend-item" key={seg.category}>
                  <span className="tm-legend-dot" style={{ background: seg.color }} />
                  {seg.label} · {seg.time}
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="tm-review-highlights">
        {highlights.map((h) => (
          <div className="tm-card tm-review-highlight" key={h.tag} style={{ borderTopColor: h.color }}>
            <span className="tm-review-tag" style={{ background: h.tBg, color: h.tFg }}>
              {h.tag}
            </span>
            <div className="tm-review-highlight-title">{h.title}</div>
            <div className={`tm-review-highlight-value${h.empty ? ' empty' : ''}`} title={h.value}>
              {h.value}
            </div>
            {h.time && (
              <div className="tm-review-highlight-time" style={{ color: `color-mix(in srgb, ${h.color} 60%, var(--tm-ink))` }}>
                {h.time}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="tm-card tm-review-suggestion">
        <span className="tm-review-suggestion-icon">💡</span>
        <div>
          <div className="tm-review-suggestion-label">다음 분석 제안</div>
          <div className="tm-review-suggestion-text">{suggestion}</div>
        </div>
      </div>

      <AiCoachingCard key={dateIso} external={external} dateIso={dateIso} onGetCoaching={onGetCoaching} />

      <div className="tm-review-stat-groups">
        <StatGroupCard title="오늘의 흐름" tag="흐름" tBg="#EAF1EC" tFg="#6F9A7C" group={flow} />
        <StatGroupCard title="집중 구간 분석" tag="집중" tBg="#F2E9F5" tFg="#8A6699" group={focus} />
      </div>
    </div>
  );
}
