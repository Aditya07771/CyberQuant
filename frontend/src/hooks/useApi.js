import { useState, useEffect, useCallback } from 'react';
import { getApiErrorMessage } from '../api/client';

/**
 * Custom hook to execute API calls with loading, error, and refetch states.
 *
 * @param {Function} apiFunc - Async function to call
 * @param {Array} deps - Dependency array for automatic trigger
 * @param {boolean} immediate - Whether to call immediately on mount (default true)
 */
export const useApi = (apiFunc, deps = [], immediate = true) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState(null);
  const [statusCode, setStatusCode] = useState(null);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    setStatusCode(null);
    try {
      const result = await apiFunc(...args);
      setData(result);
      return result;
    } catch (err) {
      const status = err.response?.status;
      setStatusCode(status);

      let message;
      if (err.code === 'NO_ACTIVE_RUN') {
        message = err.message;
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        message = 'Cannot reach the backend API. Is the FastAPI service running?';
      } else if (status === 401) {
        message = 'Your session has expired. Please sign in again.';
      } else if (status === 403) {
        message = 'You do not have permission to view this resource.';
      } else if (status === 404) {
        message = getApiErrorMessage(err, 'Requested run artifact was not found.');
      } else if (status === 503) {
        message = getApiErrorMessage(err, 'Risk artifact not available for this run.');
      } else {
        message = getApiErrorMessage(err);
      }

      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFunc]);

  useEffect(() => {
    if (immediate) {
      // Swallow the rejection here; failure is surfaced via the `error` state.
      execute().catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, statusCode, refetch: execute, setData };
};
