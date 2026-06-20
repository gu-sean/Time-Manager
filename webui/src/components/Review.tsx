import type { ReviewData, ReviewStatGroup } from '../types';

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

interface ReviewProps {
  data: ReviewData;
}

export default function Review({ data }: ReviewProps) {
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
              <div className="tm-review-highlight-time" style={{ color: h.color }}>
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

      <div className="tm-review-stat-groups">
        <StatGroupCard title="오늘의 흐름" tag="흐름" tBg="#EAF1EC" tFg="#6F9A7C" group={flow} />
        <StatGroupCard title="집중 구간 분석" tag="집중" tBg="#F2E9F5" tFg="#8A6699" group={focus} />
      </div>
    </div>
  );
}
