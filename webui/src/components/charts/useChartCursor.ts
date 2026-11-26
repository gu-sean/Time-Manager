import { useState, type KeyboardEvent } from 'react';

/**
 * 차트에서 지금 읽는 항목 관리.
 *
 * - 마우스·포커스는 보여주고, 클릭은 고정
 * - Tab 순서에는 한 항목만 포함, 항목 간 이동은 방향키
 */
export function useChartCursor(count: number, columns = count, initial = 0) {
  const [hovered, setHovered] = useState<number | null>(null);
  const [pinned, setPinned] = useState<number | null>(null);
  const [tabStop, setTabStop] = useState(initial);
  const active = hovered ?? pinned;

  const markProps = (index: number) => ({
    type: 'button' as const,
    'data-index': index,
    tabIndex: index === Math.min(tabStop, count - 1) ? 0 : -1,
    'aria-pressed': pinned === index,
    onMouseEnter: () => setHovered(index),
    onFocus: () => {
      setTabStop(index);
      setHovered(index);
    },
    onBlur: () => setHovered(null),
    onClick: () => setPinned((current) => (current === index ? null : index)),
  });

  const containerProps = {
    onMouseLeave: () => setHovered(null),
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (event.key === 'Escape') {
        setPinned(null);
        setHovered(null);
        return;
      }
      const current = Number((event.target as HTMLElement).dataset.index);
      const steps: Record<string, number> = {
        ArrowLeft: -1,
        ArrowRight: 1,
        ArrowUp: -columns,
        ArrowDown: columns,
        Home: -current,
        End: count - 1 - current,
      };
      if (!(event.key in steps) || Number.isNaN(current)) return;
      event.preventDefault();
      const next = current + steps[event.key];
      if (next < 0 || next >= count) return;
      event.currentTarget.querySelector<HTMLElement>(`[data-index="${next}"]`)?.focus();
    },
  };

  return { active, pinned, markProps, containerProps };
}
