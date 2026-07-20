import { useState } from 'react';
import type { ReportData } from '../types';

const DAILY_PAGE_SIZE = 10;

function formatHm(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}분`;
  return minutes === 0 ? `${hours}시간` : `${hours}시간 ${minutes}분`;
}

function ScoreRing({ pct }: { pct: number }) {
  return (
    <div className="tm-score-ring-wrap">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background: `conic-gradient(#BA6A49 0% ${pct}%, #EEEAE1 ${pct}% 100%)`,
        }}
      />
      <div className="tm-score-ring-center">
        <span className="tm-score-ring-value">{pct}</span>
        <span className="tm-score-ring-suffix">/ 100점</span>
      </div>
    </div>
  );
}

function TrendChart({ trend }: { trend: ReportData['trend'] }) {
  if (trend.length < 2) {
    return <div className="tm-empty-row">추세를 그리려면 2일 이상의 기록이 필요합니다.</div>;
  }
  const w = 360;
  const h = 94;
  const left = 11;
  const right = 349;
  const top = 16;
  const bottom = 84;
  const points = trend.map((point, i) => {
    const x = left + (i / (trend.length - 1)) * (right - left);
    const y = bottom - (point.score / 100) * (bottom - top);
    return [x, y] as const;
  });
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${left},${bottom} ${line} ${right},${bottom}`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: '100%', height: 120, display: 'block' }}>
      <polyline points={area} fill="rgba(186,106,73,0.1)" stroke="none" />
      <polyline points={line} fill="none" stroke="#BA6A49" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      {points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.8" fill="#FCFBF8" stroke="#BA6A49" strokeWidth="2" />
      ))}
    </svg>
  );
}

interface ReportProps {
  data: ReportData;
  onChangePeriod: (period: string) => void;
  onChangeRange: (startIso: string, endIso: string) => void;
  onExportCsv: () => void;
}

export default function Report({ data, onChangePeriod, onChangeRange, onExportCsv }: ReportProps) {
  const today = new Date().toISOString().slice(0, 10);
  const [dailyPageByPeriod, setDailyPageByPeriod] = useState<Record<string, number>>({});
  const [rangeStart, setRangeStart] = useState(today);
  const [rangeEnd, setRangeEnd] = useState(today);
  const totalPages = Math.max(1, Math.ceil(data.daily.length / DAILY_PAGE_SIZE));
  const dailyPage = Math.min(dailyPageByPeriod[data.period] ?? 0, totalPages - 1);
  const pageRows = data.daily.slice(dailyPage * DAILY_PAGE_SIZE, dailyPage * DAILY_PAGE_SIZE + DAILY_PAGE_SIZE);
  const setDailyPage = (updater: (page: number) => number) => {
    setDailyPageByPeriod((pages) => ({
      ...pages,
      [data.period]: updater(pages[data.period] ?? 0),
    }));
  };

  return (
    <div className="tm-page">
      {data.error && <div className="tm-rule-error">{data.error}</div>}
      <div className="tm-period-row">
        <div className="tm-period-chips">
          {data.periodOptions.map((opt) => (
            <button
              key={opt}
              className={`tm-period-chip${data.period === opt ? ' active' : ''}`}
              type="button"
              onClick={() => onChangePeriod(opt)}
            >
              {opt}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="date"
            className="tm-select"
            style={{ fontSize: 12, height: 28, padding: '0 6px' }}
            value={rangeStart}
            max={today}
            onChange={(e) => setRangeStart(e.target.value)}
          />
          <span style={{ fontSize: 12, color: '#B6AFA2' }}>–</span>
          <input
            type="date"
            className="tm-select"
            style={{ fontSize: 12, height: 28, padding: '0 6px' }}
            value={rangeEnd}
            max={today}
            onChange={(e) => setRangeEnd(e.target.value)}
          />
          <button
            className="tm-btn-small tm-btn-primary"
            type="button"
            onClick={() => onChangeRange(rangeStart, rangeEnd)}
          >
            조회
          </button>
          <button
            className="tm-btn-small tm-btn-ghost"
            type="button"
            onClick={onExportCsv}
          >
            CSV 내보내기
          </button>
        </div>
      </div>

      <div className="tm-report-summary-row">
        <div className="tm-card tm-score-ring-card">
          <div className="tm-card-title" style={{ alignSelf: 'flex-start' }}>
            주간 목표 점수
          </div>
          <ScoreRing pct={data.weeklyScorePct} />
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 10 }}>
            이번 기간 요약
          </div>
          <div className="tm-summary-stats">
            {data.weeklyProgressText.split(' · ').map((part, i) => (
              <div className="tm-summary-stat-row" key={i}>
                <span className="tm-summary-stat-dot" />
                <span>{part}</span>
              </div>
            ))}
          </div>
          <div className="tm-coaching-note">{data.coachingText}</div>
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 8 }}>
            요일 패턴
          </div>
          <div className="tm-weekday-chart">
            {data.weekdayBars.map((bar) => (
              <div className="tm-weekday-col" key={bar.day}>
                <span className="tm-weekday-time">{formatHm(bar.seconds)}</span>
                <div className="tm-weekday-bar-track">
                  <div
                    className="tm-weekday-bar"
                    style={{ height: `${Math.max(2, bar.pct * 0.66)}px`, background: bar.isWeekend ? '#C9C1B2' : '#BA6A49' }}
                  />
                </div>
                <span className="tm-weekday-label">{bar.day}</span>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#8A8377', marginTop: 8 }}>{data.weekdayText}</div>
        </div>
      </div>

      <div className="tm-report-2col-a">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 6 }}>
            생산성 추세
          </div>
          <div style={{ fontSize: 11, color: '#A79F92', marginBottom: 4 }}>생산성 점수 추이</div>
          <TrendChart trend={data.trend} />
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 12 }}>
            요일 · 시간 히트맵
          </div>
          {data.heatmap.map((row) => (
            <div className="tm-heatmap-row" key={row.day}>
              <span className="tm-heatmap-day-label">{row.day}</span>
              <div className="tm-heatmap-cells">
                {row.cells.map((intensity, i) => (
                  <div
                    key={i}
                    className="tm-heatmap-cell"
                    style={{ background: intensity < 0.07 ? '#F0EEE7' : `rgba(186,106,73,${0.16 + intensity * 0.66})` }}
                  />
                ))}
              </div>
            </div>
          ))}
          <div className="tm-heatmap-axis">
            <span>00시</span>
            <span>06시</span>
            <span>12시</span>
            <span>18시</span>
            <span>24시</span>
          </div>
        </div>
      </div>

      <div className="tm-report-2col-b">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 12 }}>
            일별 기록
          </div>
          <div className="tm-daily-table-head">
            <span>날짜</span>
            <span>총 시간</span>
            <span>생산적</span>
            <span style={{ textAlign: 'right' }}>점수</span>
          </div>
          {data.daily.length === 0 && <div className="tm-empty-row">기록된 데이터가 없습니다.</div>}
          {pageRows.map((row) => (
            <div className="tm-daily-table-row" key={row.day}>
              <span style={{ fontWeight: 700, color: '#3B362E' }}>{row.day}</span>
              <span style={{ color: '#6E6759' }}>{row.total}</span>
              <span style={{ fontWeight: 700, color: '#6F9A7C' }}>{row.prod}</span>
              <span style={{ textAlign: 'right', fontWeight: 800, fontSize: 13, color: '#2F2B25' }}>{row.score}</span>
            </div>
          ))}
          {data.daily.length > DAILY_PAGE_SIZE && (
            <div className="tm-daily-pagination">
              <button
                className="tm-btn-small tm-btn-ghost"
                type="button"
                disabled={dailyPage === 0}
                onClick={() => setDailyPage((p) => Math.max(0, p - 1))}
              >
                ‹ 이전
              </button>
              <span style={{ fontSize: 11, color: '#A79F92' }}>
                {dailyPage + 1} / {totalPages}
              </span>
              <button
                className="tm-btn-small tm-btn-ghost"
                type="button"
                disabled={dailyPage >= totalPages - 1}
                onClick={() => setDailyPage((p) => Math.min(totalPages - 1, p + 1))}
              >
                다음 ›
              </button>
            </div>
          )}
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 13 }}>
            TOP 활동
          </div>
          {data.topActivities.length === 0 && <div className="tm-empty-row">기록된 데이터가 없습니다.</div>}
          {data.topActivities.map((row) => (
            <div className="tm-top-activity-row" key={row.name}>
              <div className="tm-top-activity-head">
                <span style={{ fontWeight: 700, color: '#3B362E' }}>{row.name}</span>
                <span style={{ fontWeight: 700, color: '#6E6759' }}>{row.time}</span>
              </div>
              <div className="tm-top-activity-bar-track">
                <div className="tm-top-activity-bar-fill" style={{ width: `${row.ratio * 100}%`, background: row.color }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
