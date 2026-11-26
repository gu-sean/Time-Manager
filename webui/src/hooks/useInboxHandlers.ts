import { useCallback } from 'react';
import type { RefObject } from 'react';
import { deleteEvent, getInbox, reclassifyEvent, restoreDeletedEvent } from '../api';
import type { InboxData } from '../types';

export function useInboxHandlers(
  selectedDayRef: RefObject<string>,
  inbox: InboxData | null,
  setInbox: (data: InboxData) => void,
  onRecordsChanged: () => void,
  setToast: (msg: string) => void,
) {
  const handleSearch = useCallback(async (query: string, category: string | null) => {
    setInbox(await getInbox(query, category, selectedDayRef.current));
  }, []);

  const handleClearSearch = useCallback(async () => {
    setInbox(await getInbox('', null, selectedDayRef.current));
  }, []);

  // Record changes answer with today's list, so reload the view the user is looking at.
  const reloadView = async () => {
    setInbox(await getInbox(inbox?.query ?? '', inbox?.category ?? null, selectedDayRef.current));
    onRecordsChanged();
  };

  const handleDelete = async (eventId: number) => {
    await deleteEvent(eventId);
    await reloadView();
  };

  const handleRestore = async () => {
    await restoreDeletedEvent();
    await reloadView();
  };

  const handleReclassify = async (eventId: number, category: string) => {
    await reclassifyEvent(eventId, category);
    await reloadView();
    setToast('선택한 기록의 분류를 변경했습니다.');
  };

  return { handleSearch, handleClearSearch, handleDelete, handleRestore, handleReclassify };
}
