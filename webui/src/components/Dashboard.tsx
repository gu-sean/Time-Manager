import { useState } from 'react';
import FocusTimer from './FocusTimer';
import HourlyChart from './charts/HourlyChart';
import type { DashboardData } from '../types';

const CATEGORY_COLORS: Record<string, string> = {
  productive: '#128C6E',
  unproductive: '#D58528',
  neutral: '#7A82D6',
};

function Donut({ total, segments }: DashboardData['donut']) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const arcs = segments.reduce<Array<{ category: string; color: string; dash: number; offset: number }>>((acc, seg) => {
    const previous = acc.at(-1);
    const offset = previous ? previous.offset + previous.dash : 0;
    return [...acc, { category: seg.category, color: seg.color, dash: circumference * seg.ratio, offset }];
  }, []);

  return (
    <div className="tm-donut-svg-wrap">
      <svg width="134" height="134" viewBox="0 0 134 134">
        <circle cx="67" cy="67" r={radius} fill="none" stroke="#EEE9E0" strokeWidth="18" />
        {arcs.map((arc) => (
          <circle
            key={arc.category}
            cx="67"
            cy="67"
            r={radius}
            fill="none"
            stroke={arc.color}
            strokeWidth="18"
            strokeDasharray={`${arc.dash} ${circumference - arc.dash}`}
            strokeDashoffset={-arc.offset}
            transform="rotate(-90 67 67)"
          />
        ))}
      </svg>
      <div className="tm-donut-center">
        <span className="tm-donut-center-label">총 시간</span>
        <span className="tm-donut-center-value">{total}</span>
      </div>
    </div>
  );
}

const TOP_APPS_DEFAULT = 5;

function TopApps({ rows }: { rows: DashboardData['topApps'] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, TOP_APPS_DEFAULT);

  if (rows.length === 0) {
    return <div className="tm-empty-row">기록된 데이터가 없습니다.</div>;
  }
  return (
    <div className="tm-top-apps">
      {visible.map((row) => {
        const color = CATEGORY_COLORS[row.category] ?? '#7A82D6';
        const initial = [...row.label].find((ch) => /[\p{L}\p{N}]/u.test(ch))?.toUpperCase() ?? '?';
        return (
          <div className="tm-top-app-row" key={row.rank}>
            <span className="tm-top-app-rank">{row.rank}</span>
            <span className="tm-top-app-icon" style={{ background: '#F3F1EB', color }}>
              {initial}
            </span>
            <div className="tm-top-app-text">
              <div className="tm-top-app-name">{row.label}</div>
              <div className="tm-top-app-bar-track">
                <div className="tm-top-app-bar-fill" style={{ width: `${row.ratio * 100}%`, background: color }} />
              </div>
            </div>
            <span className="tm-top-app-time">{row.time}</span>
          </div>
        );
      })}
      {rows.length > TOP_APPS_DEFAULT && (
        <button
          className="tm-btn-small tm-btn-ghost"
          type="button"
          style={{ marginTop: 6, width: '100%' }}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? '접기' : `${rows.length - TOP_APPS_DEFAULT}개 더 보기`}
        </button>
      )}
    </div>
  );
}

interface DashboardProps {
  data: DashboardData;
}

export default function Dashboard({ data }: DashboardProps) {
  return (
    <div className="tm-page">
      {data.viewingToday && data.donut.segments.length === 0 && (
        <div className="tm-card tm-first-run" role="note">
          <div className="tm-card-title">아직 오늘 기록이 없어요</div>
          <div>
            {data.tracking
              ? '컴퓨터를 사용하면 잠시 후 여기에 표시돼요.'
              : '왼쪽 아래의 스위치를 켜면 활동 기록이 시작돼요.'}{' '}
            분류가 대부분 중립이라면 개인화의 직업 프리셋이나 규칙 화면에서 규칙을 추가해보세요.
          </div>
        </div>
      )}
      <div className="tm-stats-row">
        {data.stats.map((stat) => {
          // 실제 변화가 있을 때만 색 표시
          const changed = /^[▲▼]/.test(stat.delta);
          const deltaColor = !changed ? 'var(--tm-muted)' : stat.key === 'unproductive' ? 'var(--tm-danger)' : 'var(--tm-ok)';
          return (
            <div className="tm-stat-card" key={stat.key}>
              <span className="tm-stat-label">{stat.label}</span>
              <div className="tm-stat-value">{stat.value}</div>
              <div className="tm-stat-delta" style={{ color: deltaColor }}>
                {stat.delta}
              </div>
            </div>
          );
        })}
      </div>

      <div className="tm-flow-row">
        <div className="tm-card">
          <div className="tm-card-title">시간 분포</div>
          <div className="tm-donut-body">
            <Donut total={data.donut.total} segments={data.donut.segments} />
            <div className="tm-legend">
              {data.donut.segments.length === 0 && <span style={{ fontSize: 12, color: 'var(--tm-muted)' }}>기록된 데이터가 없습니다.</span>}
              {data.donut.segments.map((seg) => (
                <div className="tm-legend-row" key={seg.category}>
                  <span className="tm-legend-dot" style={{ background: seg.color }} />
                  <span className="tm-legend-label">{seg.label}</span>
                  <span className="tm-legend-pct">{seg.pct}%</span>
                  <span className="tm-legend-time">{seg.time}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="tm-card">
          <div className="tm-flow-head">
            <div className="tm-card-title">시간대별 활동 흐름</div>
            <div className="tm-flow-legend">
              <span className="tm-flow-legend-item">
                <span className="tm-flow-legend-dot" style={{ background: CATEGORY_COLORS.productive }} />
                생산적
              </span>
              <span className="tm-flow-legend-item">
                <span className="tm-flow-legend-dot" style={{ background: CATEGORY_COLORS.unproductive }} />
                비생산적
              </span>
              <span className="tm-flow-legend-item">
                <span className="tm-flow-legend-dot" style={{ background: CATEGORY_COLORS.neutral }} />
                중립
              </span>
            </div>
          </div>
          {/* 날짜가 바뀌면 선택 해제 상태로 시작 */}
          <HourlyChart key={data.dateLabel} hourly={data.hourly} viewingToday={data.viewingToday} />
        </div>
      </div>

      <div className="tm-bottom-row">
        <div className="tm-card">
          <div className="tm-card-title">상위 앱/사이트</div>
          <TopApps rows={data.topApps} />
        </div>

        <FocusTimer summary={data.focusSummary} />
      </div>
    </div>
  );
}
