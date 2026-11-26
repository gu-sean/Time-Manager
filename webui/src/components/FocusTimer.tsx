import { useSyncExternalStore } from 'react';
import { FOCUS_PRESETS, focusTimer, phaseSeconds } from '../focusTimerStore';
import { formatClock } from '../time';
import type { FocusSummary } from '../types';

const FOCUS_COLOR = '#7FA98A';
const BREAK_COLOR = '#C19A45';

function clockTime(ms: number): string {
  const at = new Date(ms);
  return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`;
}

export default function FocusTimer({ summary, viewingToday = true }: { summary?: FocusSummary; viewingToday?: boolean }) {
  const timer = useSyncExternalStore(focusTimer.subscribe, focusTimer.getState);
  const { focusMinutes, phase, remaining, endsAt, completed } = timer;
  const running = endsAt !== null;
  const total = phaseSeconds(timer);
  const progress = total > 0 ? Math.min(1, (total - remaining) / total) : 0;
  const color = phase === 'focus' ? FOCUS_COLOR : BREAK_COLOR;

  const ringStyle = {
    background: `conic-gradient(${color} ${progress * 100}%, var(--timer-track, #EEE9E0) ${progress * 100}%)`,
  };

  return (
    <div className="tm-card tm-timer-card">
      <div className="tm-timer-head">
        <div className="tm-card-title">집중 타이머</div>
        <span className="tm-timer-phase" style={{ color }}>
          {phase === 'focus' ? '집중' : '휴식'}
        </span>
      </div>

      <div className="tm-timer-ring" style={ringStyle}>
        <div className="tm-timer-ring-center">
          <span className="tm-timer-time">{formatClock(remaining)}</span>
          <span className="tm-timer-sub">{completed}회 완료</span>
        </div>
      </div>

      <div className="tm-timer-ends">{endsAt === null ? '' : `${clockTime(endsAt)}에 끝나요`}</div>

      <div className="tm-timer-presets">
        {FOCUS_PRESETS.map((m) => (
          <button
            key={m}
            type="button"
            className={`tm-timer-preset${focusMinutes === m ? ' active' : ''}`}
            onClick={() => focusTimer.selectMinutes(m)}
            aria-pressed={focusMinutes === m}
            disabled={running}
          >
            {m}분
          </button>
        ))}
      </div>

      <div className="tm-timer-actions">
        <button
          type="button"
          className="tm-btn-small tm-btn-primary tm-timer-main-btn"
          onClick={running ? focusTimer.pause : focusTimer.start}
        >
          {running ? '일시정지' : remaining === total ? '시작' : '계속'}
        </button>
        <button type="button" className="tm-btn-small tm-btn-ghost" onClick={focusTimer.reset}>
          초기화
        </button>
      </div>

      {summary && summary.count > 0 && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border, #EEE9E0)', fontSize: 11.5, color: 'var(--tm-ink-4)', textAlign: 'center' }}>
          {viewingToday ? '오늘' : '이 날'} 25분+ 집중 구간 <strong style={{ color: 'var(--tm-ok)' }}>{summary.count}개</strong>
          {summary.totalTime && <> · <strong style={{ color: 'var(--tm-ok)' }}>{summary.totalTime}</strong></>}
        </div>
      )}
    </div>
  );
}
