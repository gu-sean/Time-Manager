import { useState } from 'react';
import AskCard from './AskCard';
import Heatmap from './charts/Heatmap';
import TrendChart from './charts/TrendChart';
import { formatDuration, shortDate } from '../time';
import type { ReportData } from '../types';

const DAILY_PAGE_SIZE = 10;

/** 이 PC 시간대 기준 날짜 (toISOString 은 UTC 날짜를 반환). */
function localDate(offsetDays: number): string {
  const day = new Date();
  day.setDate(day.getDate() + offsetDays);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
}

function ScoreRing({ pct }: { pct: number }) {
  return (
    <div className="tm-score-ring-wrap">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background: `conic-gradient(#BA6A49 0% ${pct}%, var(--tm-ring-track) ${pct}% 100%)`,
        }}
      />
      <div className="tm-score-ring-center">
        <span className="tm-score-ring-value">{pct}</span>
        <span className="tm-score-ring-suffix">/ 100점</span>
      </div>
    </div>
  );
}

interface ReportProps {
  data: ReportData;
  onChangePeriod: (period: string) => void;
  onChangeRange: (startIso: string, endIso: string) => void;
  onExportCsv: () => void;
  external: boolean;
}

export default function Report({ data, onChangePeriod, onChangeRange, onExportCsv, external }: ReportProps) {
  const today = localDate(0);
  const [dailyPageByPeriod, setDailyPageByPeriod] = useState<Record<string, number>>({});
  const [rangeStart, setRangeStart] = useState(() => localDate(-6));
  const [rangeEnd, setRangeEnd] = useState(today);
  const rangeValid = !!rangeStart && !!rangeEnd && rangeStart <= rangeEnd;
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
      <AskCard external={external} />
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
        <div className="tm-range-controls">
          <input
            aria-label="시작 날짜"
            type="date"
            className="tm-select"
            style={{ fontSize: 12, height: 28, padding: '0 6px' }}
            value={rangeStart}
            max={today}
            onChange={(e) => setRangeStart(e.target.value)}
          />
          <span style={{ fontSize: 12, color: 'var(--tm-muted)' }}>–</span>
          <input
            aria-label="끝 날짜"
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
            disabled={!rangeValid}
            title={rangeValid ? undefined : '시작 날짜는 끝 날짜보다 늦을 수 없어요.'}
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
            이번 주 목표 점수
          </div>
          <ScoreRing pct={data.weeklyScorePct} />
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 10 }}>
            이번 주 목표 현황
          </div>
          <div className="tm-summary-stats">
            {data.weeklyProgressText.split(' · ').map((part, i) => (
              <div className="tm-summary-stat-row" key={i}>
                <span className="tm-summary-stat-dot" />
                <span>{part}</span>
              </div>
            ))}
          </div>
          <div className="tm-coaching-note">
            <strong>선택한 기간</strong> · {data.coachingText}
          </div>
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 8 }}>
            요일별 생산 시간 (합계)
          </div>
          <div className="tm-weekday-chart">
            {data.weekdayBars.map((bar) => (
              <div className="tm-weekday-col" key={bar.day}>
                <span className="tm-weekday-time">{formatDuration(bar.seconds)}</span>
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
          <div style={{ fontSize: 11, color: 'var(--tm-ink-4)', marginTop: 8 }}>{data.weekdayText}</div>
        </div>
      </div>

      <div className="tm-report-2col-a">
        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 6 }}>
            생산성 추세
          </div>
          <TrendChart key={`${data.startIso}~${data.endIso}`} trend={data.trend} />
        </div>

        <div className="tm-card">
          <div className="tm-card-title" style={{ marginBottom: 12 }}>
            요일 · 시간 히트맵
          </div>
          <Heatmap key={`${data.startIso}~${data.endIso}`} rows={data.heatmap} />
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
              <span style={{ fontWeight: 700, color: 'var(--tm-ink)' }}>{shortDate(row.day)}</span>
              <span style={{ color: 'var(--tm-ink-3)' }}>{row.total}</span>
              <span style={{ fontWeight: 700, color: 'var(--tm-ok)' }}>{row.prod}</span>
              <span style={{ textAlign: 'right', fontWeight: 800, fontSize: 13, color: 'var(--tm-ink)' }}>{row.score}</span>
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
              <span style={{ fontSize: 11, color: 'var(--tm-muted)' }}>
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
                <span style={{ fontWeight: 700, color: 'var(--tm-ink)' }}>{row.name}</span>
                <span style={{ fontWeight: 700, color: 'var(--tm-ink-3)' }}>{row.time}</span>
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
