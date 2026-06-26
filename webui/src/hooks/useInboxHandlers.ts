import { useCallback } from 'react';
import type { RefObject } from 'react';
import { deleteEvent, getInbox, restoreDeletedEvent } from '../api';
import type { InboxData } from '../types';

export function useInboxHandlers(
  selectedDayRef: RefObject<string>,
  setInbox: (data: InboxData) => void,
) {
  const handleSearch = useCallback(async (query: string, category: string | null) => {
    setInbox(await getInbox(query, category, selectedDayRef.current));
  }, []);

  const handleClearSearch = useCallback(async () => {
    setInbox(await getInbox('', null, selectedDayRef.current));
  }, []);

  const handleDelete = useCallback(async (eventId: number) => {
    setInbox(await deleteEvent(eventId));
  }, []);

  const handleRestore = useCallback(async () => {
    setInbox(await restoreDeletedEvent());
  }, []);

  return { handleSearch, handleClearSearch, handleDelete, handleRestore };
}
