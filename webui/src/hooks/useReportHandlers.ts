import { useCallback, useRef } from 'react';
import { exportCsvRange, getReport, getReportRange } from '../api';
import type { ReportData } from '../types';

export function useReportHandlers(
  report: ReportData | null,
  setReport: (data: ReportData) => void,
  setToast: (msg: string) => void,
) {
  // 가장 최근에 요청한 리포트만 표시
  const latest = useRef(0);

  const show = useCallback(async (request: () => Promise<ReportData>) => {
    const mine = ++latest.current;
    const next = await request();
    if (latest.current === mine) setReport(next);
  }, [setReport]);

  const handleChangePeriod = useCallback((period: string) => show(() => getReport(period)), [show]);

  const handleChangeRange = useCallback(
    (startIso: string, endIso: string) => show(() => getReportRange(startIso, endIso)),
    [show],
  );

  const handleExportCsvReport = useCallback(async () => {
    if (!report) return;
    const result = await exportCsvRange(report.startIso, report.endIso);
    if (result.message) setToast(result.message);
  }, [report, setToast]);

  return { handleChangePeriod, handleChangeRange, handleExportCsvReport };
}
