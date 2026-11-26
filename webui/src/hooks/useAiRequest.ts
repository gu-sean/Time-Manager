import { useCallback, useEffect, useRef, useState } from 'react';
import { cancelAiRequest } from '../api';

const newRequestId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;

/**
 * One cancellable analysis at a time. Answers that arrive after a cancel (or after
 * the component is gone) are dropped, so they never overwrite what is on screen.
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

  // Leaving the page stops the request instead of letting the model keep working.
  useEffect(() => () => void cancel(), [cancel]);

  /** Resolves to null when the request was cancelled or replaced. */
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
