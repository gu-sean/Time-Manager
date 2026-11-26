import { parseIsoDate, shortDate } from '../../time';
import type { TrendPoint } from '../../types';
import { useChartCursor } from './useChartCursor';

const GRID = [100, 50, 0];
const DAY_MS = 86_400_000;

const dayNumber = (iso: string) => Math.round(parseIsoDate(iso).getTime() / DAY_MS);

function isoOf(day: number, firstIso: string): string {
  const date = parseIsoDate(firstIso);
  date.setDate(date.getDate() + day - dayNumber(firstIso));
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

/** 점은 날짜 위치에 배치: 기록 없는 날이 빈칸으로 보임. */
export default function TrendChart({ trend }: { trend: TrendPoint[] }) {
  const { active, pinned, markProps, containerProps } = useChartCursor(trend.length, trend.length, trend.length - 1);

  if (trend.length < 2) {
    return <div className="tm-empty-row">추세를 그리려면 2일 이상의 기록이 필요합니다.</div>;
  }

  const first = dayNumber(trend[0].date);
  const span = Math.max(1, dayNumber(trend[trend.length - 1].date) - first);
  const xOf = (day: number) => ((day - first) / span) * 100;
  const points = trend.map((point) => ({ ...point, x: xOf(dayNumber(point.date)), y: 100 - point.score }));
  const line = points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');
  const tickCount = Math.min(4, span + 1);
  const ticks = Array.from({ length: tickCount }, (_, i) => first + Math.round((span * i) / (tickCount - 1)));
  const shown = active === null ? null : trend[active];
  const latest = trend[trend.length - 1];
  const best = trend.reduce((top, point) => (point.score > top.score ? point : top));

  return (
    <>
      <div className="tm-chart-readout">
        {shown ? (
          <>
            <strong>{shortDate(shown.date)}</strong>
            <span>생산성 점수 {shown.score}점</span>
          </>
        ) : (
          <>
            <span>
              마지막 기록 <strong>{shortDate(latest.date)}</strong> {latest.score}점
            </span>
            <span>
              최고 <strong>{shortDate(best.date)}</strong> {best.score}점
            </span>
          </>
        )}
      </div>

      <div className="tm-trend-plot">
        <div className="tm-trend-scale" aria-hidden="true">
          {GRID.map((value) => (
            <span key={value} style={{ top: `${100 - value}%` }}>
              {value}점
            </span>
          ))}
        </div>
        <div className={`tm-trend-area${trend.length > 45 ? ' dense' : ''}`} role="group" aria-label="날짜별 생산성 점수" {...containerProps}>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {GRID.map((value) => (
              <line key={value} className="tm-trend-grid" x1="0" x2="100" y1={100 - value} y2={100 - value} />
            ))}
            <polygon points={`${points[0].x},100 ${line} ${points[points.length - 1].x},100`} fill="rgba(186,106,73,0.1)" />
            <polyline className="tm-trend-line" points={line} />
          </svg>
          {points.map((point, index) => {
            // 날짜별 마우스 인식 영역은 이웃과의 중간까지
            const from = index === 0 ? 0 : (points[index - 1].x + point.x) / 2;
            const to = index === points.length - 1 ? 100 : (point.x + points[index + 1].x) / 2;
            return (
              <button
                key={point.date}
                {...markProps(index)}
                className={`tm-trend-hit${active === index ? ' active' : ''}${pinned === index ? ' pinned' : ''}`}
                style={{ left: `${from}%`, width: `${to - from}%` }}
                aria-label={`${shortDate(point.date)}, 생산성 점수 ${point.score}점`}
              />
            );
          })}
          {points.map((point, index) => (
            <span
              key={point.date}
              className={`tm-trend-dot${active === index ? ' active' : ''}`}
              style={{ left: `${point.x}%`, top: `${point.y}%` }}
            />
          ))}
        </div>
      </div>
      <div className="tm-trend-axis" aria-hidden="true">
        {ticks.map((day, i) => (
          <span
            key={day}
            style={{
              left: `${xOf(day)}%`,
              transform: `translateX(${i === 0 ? '0' : i === ticks.length - 1 ? '-100%' : '-50%'})`,
            }}
          >
            {shortDate(isoOf(day, trend[0].date))}
          </span>
        ))}
      </div>
    </>
  );
}
