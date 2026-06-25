import { useEffect, useRef, useState } from 'react';
import { sendFocusNotification } from '../api';
import type { FocusSummary } from '../types';

type Phase = 'focus' | 'break';

const FOCUS_PRESETS = [25, 50, 15];
const BREAK_SECONDS = 5 * 60;
const FOCUS_COLOR = '#7FA98A';
const BREAK_COLOR = '#C19A45';

function format(seconds: number): string {
  const m = String(Math.floor(seconds / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${m}:${s}`;
}

export default function FocusTimer({ summary }: { summary?: FocusSummary }) {
  const [focusMinutes, setFocusMinutes] = useState(FOCUS_PRESETS[0]);
  const [phase, setPhase] = useState<Phase>('focus');
  const [remaining, setRemaining] = useState(FOCUS_PRESETS[0] * 60);
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(0);

  const total = phase === 'focus' ? focusMinutes * 60 : BREAK_SECONDS;
  const progress = total > 0 ? Math.min(1, (total - remaining) / total) : 0;
  const color = phase === 'focus' ? FOCUS_COLOR : BREAK_COLOR;

  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const focusRef = useRef(focusMinutes);
  focusRef.current = focusMinutes;

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => {
      setRemaining((prev) => {
        if (prev > 1) return prev - 1;
        // phase finished
        if (phaseRef.current === 'focus') {
          setCompleted((c) => c + 1);
          setPhase('break');
          setRunning(false);
          void sendFocusNotification('집중 완료', `${focusRef.current}분 집중을 마쳤어요. 잠깐 쉬어요.`);
          return BREAK_SECONDS;
        }
        setPhase('focus');
        setRunning(false);
        void sendFocusNotification('휴식 종료', '다시 집중해볼까요?');
        return focusRef.current * 60;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [running]);

  const selectPreset = (minutes: number) => {
    setFocusMinutes(minutes);
    if (phase === 'focus' && !running) setRemaining(minutes * 60);
  };

  const reset = () => {
    setRunning(false);
    setPhase('focus');
    setRemaining(focusMinutes * 60);
  };

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
          <span className="tm-timer-time">{format(remaining)}</span>
          <span className="tm-timer-sub">{completed}회 완료</span>
        </div>
      </div>

      <div className="tm-timer-presets">
        {FOCUS_PRESETS.map((m) => (
          <button
            key={m}
            type="button"
            className={`tm-timer-preset${focusMinutes === m ? ' active' : ''}`}
            onClick={() => selectPreset(m)}
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
          onClick={() => setRunning((r) => !r)}
        >
          {running ? '일시정지' : remaining === total ? '시작' : '계속'}
        </button>
        <button type="button" className="tm-btn-small tm-btn-ghost" onClick={reset}>
          초기화
        </button>
      </div>

      {summary && summary.count > 0 && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border, #EEE9E0)', fontSize: 11.5, color: '#8A8377', textAlign: 'center' }}>
          오늘 25분+ 집중 구간 <strong style={{ color: FOCUS_COLOR }}>{summary.count}개</strong>
          {summary.totalTime && <> · <strong style={{ color: FOCUS_COLOR }}>{summary.totalTime}</strong></>}
        </div>
      )}
    </div>
  );
}
