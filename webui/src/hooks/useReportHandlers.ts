import { useCallback } from 'react';
import { exportCsvRange, getReport, getReportRange } from '../api';
import type { ReportData } from '../types';

export function useReportHandlers(
  report: ReportData | null,
  setReport: (data: ReportData) => void,
  setToast: (msg: string) => void,
) {
  const handleChangePeriod = useCallback(async (period: string) => {
    setReport(await getReport(period));
  }, []);

  const handleChangeRange = useCallback(async (startIso: string, endIso: string) => {
    setReport(await getReportRange(startIso, endIso));
  }, []);

  const handleExportCsvReport = useCallback(async () => {
    if (!report) return;
    const result = await exportCsvRange(report.startIso, report.endIso);
    if (result.message) setToast(result.message);
  }, [report]);

  return { handleChangePeriod, handleChangeRange, handleExportCsvReport };
}
