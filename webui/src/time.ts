const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export function formatDuration(seconds: number): string {
  if (seconds <= 0) return '0분';
  if (seconds < 60) return '1분 미만';
  const totalMinutes = Math.floor(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}분`;
  return minutes === 0 ? `${hours}시간` : `${hours}시간 ${minutes}분`;
}

/** 남은 시간 표시 (예: "04:09"). */
export function formatClock(seconds: number): string {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

/** `hour` 시에 시작하는 한 시간 (예: "14시–15시"). */
export function hourRange(hour: number): string {
  return `${hour}시–${hour + 1}시`;
}

/** YYYY-MM-DD 를 이 PC의 날짜로 해석 (new Date(iso) 는 UTC 로 해석). */
export function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
}

/** "11/26 (목)" */
export function shortDate(iso: string): string {
  const date = parseIsoDate(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.getMonth() + 1}/${date.getDate()} (${WEEKDAYS[date.getDay()]})`;
}
