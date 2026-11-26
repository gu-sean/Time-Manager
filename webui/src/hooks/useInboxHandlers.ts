import { useCallback, useRef } from 'react';
import type { RefObject } from 'react';
import { addManualEntry, addRuleForEvent, deleteEvent, deleteTargetRecords, getInbox, reclassifyEvent, restoreDeletedEvent } from '../api';
import type { InboxData, ManualEntry } from '../types';

export function useInboxHandlers(
  selectedDayRef: RefObject<string>,
  inbox: InboxData | null,
  setInbox: (data: InboxData) => void,
  onRecordsChanged: () => void,
  setToast: (msg: string) => void,
) {
  // 늦게 끝난 이전 검색이 이후 검색 결과를 덮지 않게 함
  const latest = useRef(0);

  const search = useCallback(async (query: string, category: string | null) => {
    const mine = ++latest.current;
    const next = await getInbox(query, category, selectedDayRef.current);
    if (latest.current === mine) setInbox(next);
  }, [selectedDayRef, setInbox]);

  const handleSearch = useCallback((query: string, category: string | null) => search(query, category), [search]);

  const handleClearSearch = useCallback(() => search('', null), [search]);

  // 기록 변경 API 는 오늘 목록을 반환 → 보고 있던 화면을 다시 로드
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

  const handleAddRule = async (eventId: number) => {
    const result = await addRuleForEvent(eventId);
    await reloadView();
    setToast(result.error || result.message);
  };

  const handleDeleteTarget = async (eventId: number) => {
    const result = await deleteTargetRecords(eventId);
    await reloadView();
    setToast(result.error || result.message);
  };

  /** 문제가 있으면 그 문구, 추가했으면 "" */
  const handleAddManual = async (entry: ManualEntry): Promise<string> => {
    const result = await addManualEntry(selectedDayRef.current, entry.start, entry.minutes, entry.label, entry.category);
    if (result.error) return result.error;
    await reloadView();
    setToast(result.message);
    return '';
  };

  return {
    handleSearch, handleClearSearch, handleDelete, handleRestore, handleReclassify, handleAddRule,
    handleDeleteTarget, handleAddManual,
  };
}
