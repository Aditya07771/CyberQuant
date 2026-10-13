import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  listDatasets,
  listRuns,
  createDataset,
  startRun,
  getJob,
  setActiveScope,
} from '../api/client';
import { useAuth } from './AuthContext';

const DatasetContext = createContext(null);

const EXCEL_SUMMARY_STORAGE_KEY = 'cyberquant.excelSummary';
const TERMINAL_JOB_STATES = ['succeeded', 'failed'];

export function DatasetProvider({ children }) {
  const { isAuthenticated } = useAuth();

  const [datasets, setDatasets] = useState([]);
  const [activeDatasetId, setActiveDatasetId] = useState(null);
  const [runs, setRuns] = useState([]);
  const [activeRunId, setActiveRunId] = useState(null);
  const [activeRun, setActiveRun] = useState(null);
  const [job, setJob] = useState(null);
  // idle | ingesting | running | ready | error
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [excelSummary, setExcelSummaryState] = useState(() => {
    try {
      const raw = localStorage.getItem(EXCEL_SUMMARY_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  // Keep the API client's active dataset/run scope in sync.
  useEffect(() => {
    setActiveScope({ datasetId: activeDatasetId, runId: activeRunId });
  }, [activeDatasetId, activeRunId]);

  const setExcelSummary = useCallback((summary) => {
    setExcelSummaryState(summary || null);
    try {
      if (summary) {
        localStorage.setItem(EXCEL_SUMMARY_STORAGE_KEY, JSON.stringify(summary));
      } else {
        localStorage.removeItem(EXCEL_SUMMARY_STORAGE_KEY);
      }
    } catch {
      /* ignore storage errors */
    }
  }, []);

  const resetDataset = useCallback(() => {
    setActiveDatasetId(null);
    setActiveRunId(null);
    setActiveRun(null);
    setRuns([]);
    setJob(null);
    setStatus('idle');
    setError(null);
    setExcelSummary(null);
    setActiveScope({ datasetId: null, runId: null });
  }, [setExcelSummary]);

  const refreshDatasets = useCallback(async () => {
    const list = await listDatasets();
    setDatasets(list);
    return list;
  }, []);

  const selectRun = useCallback((runId, runObj = null) => {
    setActiveRunId(runId || null);
    setActiveRun(runObj || null);
    // Sync the API scope immediately so children re-fetching on the next render
    // (their effects run before this provider's) read the correct run.
    setActiveScope({ datasetId: activeDatasetId, runId: runId || null });
  }, [activeDatasetId]);

  const selectDataset = useCallback(async (datasetId) => {
    setActiveDatasetId(datasetId);
    setActiveRunId(null);
    setActiveRun(null);
    setActiveScope({ datasetId, runId: null });
    try {
      const list = await listRuns(datasetId);
      setRuns(list);
      const completed = list.find((r) => r.state === 'completed');
      if (completed) {
        setActiveRunId(completed.id);
        setActiveRun(completed);
      }
      setActiveScope({ datasetId, runId: completed?.id || null });
      return { runs: list, activeRun: completed || null };
    } catch {
      setRuns([]);
      return { runs: [], activeRun: null };
    }
  }, []);

  const waitForJob = useCallback(async (jobId) => {
    // Poll until the job reaches a terminal state. Bounded by the backend's own
    // job timeout; we surface a safe error rather than polling forever blindly.
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const j = await getJob(jobId);
      setJob(j);
      if (TERMINAL_JOB_STATES.includes(j.state)) return j;
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
  }, []);

  const ingestDataset = useCallback(
    async ({ name, description = null, datasetType = 'tabular', files }) => {
      setError(null);
      setStatus('ingesting');
      try {
        const res = await createDataset({ name, description, datasetType, files });
        setActiveDatasetId(res.dataset_id);

        const ingestJob = await waitForJob(res.job_id);
        if (ingestJob.state === 'failed') {
          const msg = ingestJob.safe_error_message || 'Dataset ingestion failed.';
          setStatus('error');
          setError(msg);
          throw new Error(msg);
        }

        setStatus('running');
        const runRes = await startRun(res.dataset_id);
        const runJob = await waitForJob(runRes.job_id);
        if (runJob.state === 'failed') {
          const msg = runJob.safe_error_message || 'Risk quantification run failed.';
          setStatus('error');
          setError(msg);
          throw new Error(msg);
        }

        const list = await listRuns(res.dataset_id);
        setRuns(list);
        const completed = list.find((r) => r.state === 'completed') || list[0] || null;
        setActiveRunId(completed?.id || null);
        setActiveRun(completed);
        setActiveScope({ datasetId: res.dataset_id, runId: completed?.id || null });
        setStatus('ready');
        refreshDatasets().catch(() => {});
        return { datasetId: res.dataset_id, runId: completed?.id || null };
      } catch (err) {
        setStatus('error');
        setError(err?.message || 'Dataset processing failed.');
        throw err;
      }
    },
    [waitForJob, refreshDatasets],
  );

  const checkStatus = useCallback(async () => {
    if (!isAuthenticated) {
      setIsCheckingStatus(false);
      return;
    }
    try {
      const list = await listDatasets();
      setDatasets(list);
      if (list.length > 0 && !activeDatasetId) {
        for (const d of list) {
          try {
            const rl = await listRuns(d.id);
            const completed = rl.find((r) => r.state === 'completed');
            if (completed) {
              setActiveDatasetId(d.id);
              setRuns(rl);
              setActiveRunId(completed.id);
              setActiveRun(completed);
              setActiveScope({ datasetId: d.id, runId: completed.id });
              break;
            }
          } catch {
            /* skip datasets we cannot read */
          }
        }
      }
    } catch {
      /* backend offline or unauthorized; UI shows empty state */
    } finally {
      setIsCheckingStatus(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, activeDatasetId]);

  useEffect(() => {
    if (!isAuthenticated) {
      resetDataset();
      setIsCheckingStatus(false);
      return;
    }
    setIsCheckingStatus(true);
    checkStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  // Keep the active run object in sync with the runs list.
  useEffect(() => {
    if (activeRunId) {
      const found = runs.find((r) => r.id === activeRunId);
      if (found) setActiveRun(found);
    }
  }, [runs, activeRunId]);

  const hasDataset = Boolean(activeRunId);
  const datasetMeta = {
    datasetId: activeDatasetId,
    runId: activeRunId,
    run: activeRun,
    assetCount: activeRun?.summary_metrics?.asset_count,
    lastUpdated: activeRun?.finished_at,
  };

  const value = {
    datasets,
    activeDatasetId,
    activeRunId,
    activeRun,
    runs,
    job,
    status,
    error,
    hasDataset,
    datasetMeta,
    isCheckingStatus,
    excelSummary,
    setExcelSummary,
    refreshDatasets,
    selectDataset,
    selectRun,
    ingestDataset,
    resetDataset,
    checkStatus,
  };

  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

export const useDataset = () => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
};
