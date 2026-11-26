/** 앱 호출이 실패했을 때 사용자에게 보여줄 문장. */
export function describeError(reason: unknown): string {
  const error = reason as { name?: string; message?: string } | undefined;
  const text = `${error?.name ?? ''} ${error?.message ?? ''}`;
  if (/database is locked/i.test(text)) return '기록 데이터가 잠겨 있어요. 잠시 후 다시 시도하세요.';
  if (/PermissionError|Permission denied|Errno 13/i.test(text)) {
    return '파일에 쓸 권한이 없어 저장하지 못했어요. 파일이 다른 프로그램에서 열려 있는지, 데이터 폴더 권한을 확인하세요.';
  }
  if (/No space left|Errno 28|disk is full/i.test(text)) return '디스크 공간이 부족해 저장하지 못했어요.';
  if (/OSError|sqlite3|OperationalError|DatabaseError/i.test(text)) {
    return '데이터를 읽거나 쓰지 못했어요. 디스크와 데이터 폴더를 확인한 뒤 다시 시도하세요.';
  }
  return '작업을 완료하지 못했어요. 다시 시도해주세요.';
}
