import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getDatasetStatus } from '../api/client';

const DatasetContext = createContext(null);

const EXCEL_SUMMARY_STORAGE_KEY = 'cyberquant.excelSummary';

export const DatasetProvider = ({ children }) => {
  const [hasDataset, setHasDataset] = useState(false);
  const [datasetMeta, setDatasetMeta] = useState(null);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [excelSummary, setExcelSummary] = useState(() => {
    try {
      const raw = localStorage.getItem(EXCEL_SUMMARY_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const checkStatus = useCallback(async () => {
    try {
      const status = await getDatasetStatus();
      if (status?.outputs_ready) {
        setHasDataset(true);
        setDatasetMeta({
          assetCount: status.asset_count,
          lastUpdated: status.last_updated,
        });
      }
    } catch {
      // Backend might be offline or outputs not ready
    } finally {
      setIsCheckingStatus(false);
    }
  }, []);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const setDatasetLoaded = (meta) => {
    setHasDataset(true);
    setDatasetMeta(meta || {});
    if (meta && meta.excelSummary) {
      setExcelSummary(meta.excelSummary);
      try {
        localStorage.setItem(EXCEL_SUMMARY_STORAGE_KEY, JSON.stringify(meta.excelSummary));
      } catch {
        // Ignore storage errors (e.g. private mode)
      }
    } else if (meta) {
      setExcelSummary(null);
      try {
        localStorage.removeItem(EXCEL_SUMMARY_STORAGE_KEY);
      } catch {
        // Ignore
      }
    }
  };

  const resetDataset = () => {
    setHasDataset(false);
    setDatasetMeta(null);
    setExcelSummary(null);
    try {
      localStorage.removeItem(EXCEL_SUMMARY_STORAGE_KEY);
    } catch {
      // Ignore
    }
  };

  return (
    <DatasetContext.Provider
      value={{
        hasDataset,
        datasetMeta,
        isCheckingStatus,
        excelSummary,
        setDatasetLoaded,
        resetDataset,
        checkStatus,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
};

export const useDataset = () => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error('useDataset must be used within a DatasetProvider');
  }
  return context;
};
