// 타이머는 대시보드 밖에 둠: 다른 화면으로 가도 초기화되지 않음
// 매번 1초씩 빼지 않고 종료 시각 기준으로 계산
// (최소화한 창은 타이머 실행이 늦어짐)
import { sendFocusNotification } from './api';

export const FOCUS_PRESETS = [15, 25, 50];
const DEFAULT_FOCUS_MINUTES = 25;
const BREAK_SECONDS = 5 * 60;

export interface FocusTimerState {
  focusMinutes: number;
  phase: 'focus' | 'break';
  remaining: number;
  /** 진행 중인 단계가 끝나는 시각 (epoch ms). 멈춘 상태면 null. */
  endsAt: number | null;
  completed: number;
}

let state: FocusTimerState = {
  focusMinutes: DEFAULT_FOCUS_MINUTES,
  phase: 'focus',
  remaining: DEFAULT_FOCUS_MINUTES * 60,
  endsAt: null,
  completed: 0,
};
const listeners = new Set<() => void>();
let ticker: number | undefined;
let alarm: number | undefined;

function update(patch: Partial<FocusTimerState>) {
  state = { ...state, ...patch };
  listeners.forEach((listener) => listener());
}

function stopClocks() {
  window.clearInterval(ticker);
  window.clearTimeout(alarm);
}

export function phaseSeconds(current: FocusTimerState): number {
  return current.phase === 'focus' ? current.focusMinutes * 60 : BREAK_SECONDS;
}

function secondsLeft(endsAt: number): number {
  return Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
}

function finishPhase() {
  stopClocks();
  if (state.phase === 'focus') {
    void sendFocusNotification('집중 완료', `${state.focusMinutes}분 집중을 마쳤어요. 잠깐 쉬어요.`);
    update({ phase: 'break', remaining: BREAK_SECONDS, endsAt: null, completed: state.completed + 1 });
  } else {
    void sendFocusNotification('휴식 종료', '다시 집중해볼까요?');
    update({ phase: 'focus', remaining: state.focusMinutes * 60, endsAt: null });
  }
}

function tick() {
  if (state.endsAt === null) return;
  const left = secondsLeft(state.endsAt);
  if (left === 0) finishPhase();
  else if (left !== state.remaining) update({ remaining: left });
}

export const focusTimer = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
  getState: () => state,
  start() {
    if (state.endsAt !== null) return;
    stopClocks();
    update({ endsAt: Date.now() + state.remaining * 1000 });
    ticker = window.setInterval(tick, 250);
    alarm = window.setTimeout(tick, state.remaining * 1000);
  },
  pause() {
    if (state.endsAt === null) return;
    const left = secondsLeft(state.endsAt);
    if (left === 0) {
      finishPhase();
      return;
    }
    stopClocks();
    update({ remaining: left, endsAt: null });
  },
  reset() {
    stopClocks();
    update({ phase: 'focus', remaining: state.focusMinutes * 60, endsAt: null });
  },
  /** 길이를 바꾸면 멈춘 집중 단계는 새로 시작, 휴식 중이면 다음 집중에 적용. */
  selectMinutes(minutes: number) {
    if (state.endsAt !== null || minutes === state.focusMinutes) return;
    update(state.phase === 'focus' ? { focusMinutes: minutes, remaining: minutes * 60 } : { focusMinutes: minutes });
  },
};
