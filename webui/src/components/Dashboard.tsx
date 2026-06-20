import FocusTimer from './FocusTimer';
import type { DashboardData } from '../types';

const CATEGORY_COLORS: Record<string, string> = {
  productive: '#7FA98A',
  unproductive: '#DB9163',
  neutral: '#99ABBE',
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

function HourlyChart({ hourly }: { hourly: DashboardData['hourly'] }) {
  const peak = Math.max(1, ...hourly.map((h) => h.productive + h.unproductive + h.neutral));
  return (
    <>
      <div className="tm-hourly-chart">
        {hourly.map((h) => {
          const total = h.productive + h.unproductive + h.neutral;
          const pPct = (h.productive / peak) * 100;
          const uPct = (h.unproductive / peak) * 100;
          const nPct = (h.neutral / peak) * 100;
          return (
            <div className="tm-hourly-bar" key={h.hour} title={`${h.hour}시 · ${total}s`}>
              <div style={{ height: `${nPct}%`, background: CATEGORY_COLORS.neutral, borderRadius: '3px 3px 0 0' }} />
              <div style={{ height: `${uPct}%`, background: CATEGORY_COLORS.unproductive }} />
              <div style={{ height: `${pPct}%`, background: CATEGORY_COLORS.productive, borderRadius: '0 0 3px 3px' }} />
            </div>
          );
        })}
      </div>
      <div className="tm-hourly-axis">
        <span>00:00</span>
        <span>04:00</span>
        <span>08:00</span>
        <span>12:00</span>
        <span>16:00</span>
        <span>20:00</span>
        <span>24:00</span>
      </div>
    </>
  );
}

function TopApps({ rows }: { rows: DashboardData['topApps'] }) {
  if (rows.length === 0) {
    return <div className="tm-top-apps">기록된 데이터가 없습니다.</div>;
  }
  return (
    <div className="tm-top-apps">
      {rows.map((row) => {
        const color = CATEGORY_COLORS[row.category] ?? '#99ABBE';
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
    </div>
  );
}

interface DashboardProps {
  data: DashboardData;
  onToggleFocus: (enabled: boolean) => void;
}

export default function Dashboard({ data, onToggleFocus }: DashboardProps) {
  return (
    <div className="tm-page">
      <div className="tm-stats-row">
        {data.stats.map((stat) => {
          const deltaColor = stat.key === 'unproductive' ? '#C8795A' : '#6F9A7C';
          return (
            <div className="tm-stat-card" key={stat.key}>
              <div className="tm-stat-head">
                <span className="tm-stat-label">{stat.label}</span>
                <div className="tm-stat-badge" style={{ background: stat.badge.bg, color: stat.badge.fg }}>
                  {stat.badge.glyph}
                </div>
              </div>
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
              {data.donut.segments.length === 0 && <span style={{ fontSize: 12, color: '#A79F92' }}>기록된 데이터가 없습니다.</span>}
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
          <HourlyChart hourly={data.hourly} />
        </div>
      </div>

      <div className="tm-card">
        <div className="tm-card-title">상위 앱/사이트</div>
        <TopApps rows={data.topApps} />
      </div>

      <div className="tm-focus-row">
        <FocusTimer />

        <div className="tm-card tm-focus-card">
          <div className="tm-focus-head">
            <div className="tm-card-title">집중 알림</div>
            <button
              className={`tm-toggle-track ${data.focusMode.enabled ? 'on' : 'off'}`}
              type="button"
              onClick={() => onToggleFocus(!data.focusMode.enabled)}
              aria-label="집중 알림 토글"
            >
              <span className="tm-toggle-knob" />
            </button>
          </div>
          <div className="tm-focus-desc">
            비생산 활동이 {data.focusMode.thresholdMinutes}분 연속되면 알림을 보내드려요.
          </div>
          <div className="tm-focus-status">
            <div className="tm-focus-streak-label">현재 연속 비생산 시간</div>
            <div className="tm-focus-streak-value">{data.focusMode.streakLabel}</div>
          </div>
          <div className="tm-focus-bar-row">
            <div className="tm-focus-bar-track">
              <div className="tm-focus-bar-fill" style={{ width: `${data.focusMode.ratio * 100}%` }} />
            </div>
            <span className="tm-focus-bar-label">{data.focusMode.thresholdMinutes}분</span>
          </div>
        </div>
      </div>
    </div>
  );
}
