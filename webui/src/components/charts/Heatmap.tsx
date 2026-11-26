import { formatDuration, hourRange } from '../../time';
import type { HeatmapRow } from '../../types';
import { useChartCursor } from './useChartCursor';

const HOURS = 24;

const shade = (intensity: number) => `rgba(186,106,73,${0.16 + intensity * 0.66})`;

export default function Heatmap({ rows }: { rows: HeatmapRow[] }) {
  const { active, pinned, markProps, containerProps } = useChartCursor(rows.length * HOURS, HOURS);

  const cells = rows.flatMap((row) => row.seconds.map((seconds, hour) => ({ day: row.day, hour, seconds })));
  const busiest = cells.reduce<(typeof cells)[number] | null>(
    (best, cell) => (cell.seconds > (best?.seconds ?? 0) ? cell : best),
    null,
  );
  const shown = active === null ? null : cells[active];
  const activeHour = shown?.hour;

  return (
    <>
      <div className="tm-chart-readout">
        {shown ? (
          <>
            <strong>
              {shown.day}요일 {hourRange(shown.hour)}
            </strong>
            <span>{shown.seconds > 0 ? `합계 ${formatDuration(shown.seconds)}` : '기록 없음'}</span>
          </>
        ) : busiest ? (
          <span>
            가장 많이 쓴 때{' '}
            <strong>
              {busiest.day}요일 {hourRange(busiest.hour)}
            </strong>{' '}
            (합계 {formatDuration(busiest.seconds)})
          </span>
        ) : (
          <span>이 기간에는 기록이 없어요.</span>
        )}
      </div>

      <div role="group" aria-label="요일과 시간대별 사용 시간" {...containerProps}>
        {rows.map((row, rowIndex) => (
          <div className="tm-heatmap-row" key={row.day}>
            <span className={`tm-heatmap-day-label${shown?.day === row.day ? ' active' : ''}`}>{row.day}</span>
            <div className="tm-heatmap-cells">
              {row.cells.map((intensity, hour) => {
                const index = rowIndex * HOURS + hour;
                return (
                  <button
                    key={hour}
                    {...markProps(index)}
                    className={`tm-heatmap-cell${active === index ? ' active' : ''}${pinned === index ? ' pinned' : ''}`}
                    style={{ background: row.seconds[hour] > 0 ? shade(intensity) : 'var(--tm-cell-empty)' }}
                    aria-label={`${row.day}요일 ${hourRange(hour)}, ${row.seconds[hour] > 0 ? `합계 ${formatDuration(row.seconds[hour])}` : '기록 없음'}`}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div className="tm-heatmap-axis" aria-hidden="true">
        {Array.from({ length: HOURS }, (_, hour) => (
          <span key={hour} className={hour === activeHour ? 'active' : undefined}>
            {hour % 3 === 0 ? `${hour}시` : ''}
          </span>
        ))}
      </div>
      <div className="tm-heatmap-legend">
        <span>전체 사용 시간</span>
        <span className="tm-heatmap-swatch" style={{ background: 'var(--tm-cell-empty)' }} />
        <span>없음</span>
        <span>· 적음</span>
        {[0.05, 0.35, 0.65, 1].map((step) => (
          <span key={step} className="tm-heatmap-swatch" style={{ background: shade(step) }} />
        ))}
        <span>많음</span>
      </div>
    </>
  );
}
