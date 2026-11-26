import { useState } from 'react';
import { formatDuration, hourRange } from '../../time';
import type { HourlyRow } from '../../types';
import { useChartCursor } from './useChartCursor';

/** 아래에서부터 이 순서로 쌓음. */
const SERIES = [
  { key: 'productive', label: '생산적', color: '#128C6E' },
  { key: 'unproductive', label: '비생산적', color: '#D58528' },
  { key: 'neutral', label: '중립', color: '#7A82D6' },
] as const;

const totalOf = (row: HourlyRow) => row.productive + row.unproductive + row.neutral;

export default function HourlyChart({ hourly, viewingToday }: { hourly: HourlyRow[]; viewingToday: boolean }) {
  const [showTable, setShowTable] = useState(false);
  const nowHour = viewingToday ? new Date().getHours() : -1;
  const { active, pinned, markProps, containerProps } = useChartCursor(hourly.length, hourly.length, Math.max(0, nowHour));

  const used = hourly.filter((row) => totalOf(row) > 0);
  // 가득 찬 막대 = 1시간: 어느 날이든 높이의 의미가 같음
  const scale = Math.max(3600, ...hourly.map(totalOf));
  const busiest = used.reduce<HourlyRow | null>((best, row) => (!best || totalOf(row) > totalOf(best) ? row : best), null);
  const shown = active === null ? null : hourly[active];

  return (
    <>
      <div className="tm-chart-readout">
        {shown ? (
          <>
            <strong>{hourRange(shown.hour)}</strong>
            {totalOf(shown) === 0 ? (
              <span>기록 없음</span>
            ) : (
              <>
                <span>총 {formatDuration(totalOf(shown))}</span>
                {SERIES.filter((series) => shown[series.key] > 0).map((series) => (
                  <span key={series.key} className="tm-chart-readout-item">
                    <span className="tm-flow-legend-dot" style={{ background: series.color }} />
                    {series.label} {formatDuration(shown[series.key])}
                  </span>
                ))}
              </>
            )}
          </>
        ) : busiest ? (
          <>
            <span>
              활동 시간대 <strong>{used[0].hour}시–{used[used.length - 1].hour + 1}시</strong>
            </span>
            <span>
              가장 많이 쓴 때 <strong>{hourRange(busiest.hour)}</strong> ({formatDuration(totalOf(busiest))})
            </span>
          </>
        ) : (
          <span>아직 기록된 시간이 없어요.</span>
        )}
      </div>

      <div className="tm-hourly-plot">
        <div className="tm-hourly-scale" aria-hidden="true">
          <span style={{ bottom: '100%' }}>60분</span>
          <span style={{ bottom: '50%' }}>30분</span>
          <span style={{ bottom: 0 }}>0</span>
        </div>
        <div className="tm-hourly-chart" role="group" aria-label="시간대별 사용 시간" {...containerProps}>
          {hourly.map((row, index) => (
            <button
              key={row.hour}
              {...markProps(index)}
              className={`tm-hourly-bar${active === index ? ' active' : ''}${pinned === index ? ' pinned' : ''}${row.hour === nowHour ? ' now' : ''}`}
              aria-label={
                totalOf(row) === 0
                  ? `${hourRange(row.hour)}, 기록 없음`
                  : `${hourRange(row.hour)}, 총 ${formatDuration(totalOf(row))}, ${SERIES.map((s) => `${s.label} ${formatDuration(row[s.key])}`).join(', ')}`
              }
            >
              {[...SERIES].reverse().map(
                (series) =>
                  row[series.key] > 0 && (
                    <span
                      key={series.key}
                      className="tm-hourly-segment"
                      style={{ height: `${(row[series.key] / scale) * 100}%`, background: series.color }}
                    />
                  ),
              )}
            </button>
          ))}
        </div>
      </div>
      <div className="tm-hourly-axis" aria-hidden="true">
        {hourly.map((row) => (
          <span key={row.hour} className={row.hour === nowHour ? 'now' : undefined}>
            {/* "지금"과 겹치는 시각 라벨은 숨김 */}
            {row.hour === nowHour ? '지금' : row.hour % 3 === 0 && (nowHour < 0 || Math.abs(row.hour - nowHour) > 1) ? `${row.hour}시` : ''}
          </span>
        ))}
      </div>

      <div className="tm-chart-foot">
        <span>막대에 마우스를 올리거나 눌러서 확인하세요.</span>
        {used.length > 0 && (
          <button
            type="button"
            className="tm-btn-small tm-btn-ghost"
            aria-expanded={showTable}
            onClick={() => setShowTable((value) => !value)}
          >
            {showTable ? '목록 닫기' : '시간별 목록'}
          </button>
        )}
      </div>

      {showTable && used.length > 0 && (
        <table className="tm-hourly-table">
          <thead>
            <tr>
              <th scope="col">시간</th>
              <th scope="col">총</th>
              {SERIES.map((series) => (
                <th scope="col" key={series.key}>
                  {series.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {used.map((row) => (
              <tr key={row.hour}>
                <th scope="row">{hourRange(row.hour)}</th>
                <td>{formatDuration(totalOf(row))}</td>
                {SERIES.map((series) => (
                  <td key={series.key}>{row[series.key] > 0 ? formatDuration(row[series.key]) : '–'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
