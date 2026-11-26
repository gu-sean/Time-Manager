import { useCallback, useEffect, useRef, useState } from 'react';
import { cancelAiRequest } from '../api';

const newRequestId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;

/**
 * 취소 가능한 분석을 한 번에 하나만 실행.
 *
 * - 취소 후(또는 컴포넌트가 사라진 뒤) 도착한 응답은 버림 → 화면을 덮지 않음
 */
export function useAiRequest() {
  const currentRef = useRef<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!loading) return undefined;
    const startedAt = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 250);
    return () => window.clearInterval(timer);
  }, [loading]);

  const cancel = useCallback(() => {
    const id = currentRef.current;
    if (!id) return false;
    currentRef.current = null;
    setLoading(false);
    void cancelAiRequest(id);
    return true;
  }, []);

  // 화면을 벗어나면 모델이 계속 작업하지 않도록 요청 중단
  useEffect(() => () => void cancel(), [cancel]);

  /** 취소되거나 새 요청으로 대체되면 null. */
  const run = useCallback(
    async <T,>(task: (requestId: string) => Promise<T>): Promise<T | null> => {
      cancel();
      const id = newRequestId();
      currentRef.current = id;
      setElapsed(0);
      setLoading(true);
      try {
        const result = await task(id);
        return currentRef.current === id ? result : null;
      } finally {
        if (currentRef.current === id) {
          currentRef.current = null;
          setLoading(false);
        }
      }
    },
    [cancel],
  );

  return { loading, elapsed, run, cancel };
}
