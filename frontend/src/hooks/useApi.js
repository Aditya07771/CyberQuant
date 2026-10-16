import { useState, useEffect, useCallback } from 'react';

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
      
      let message = err.response?.data?.detail || err.message || 'An unexpected error occurred';
      
      if (status === 503) {
        message = 'Risk data not available. Has the pipeline been run? (Run `python -m risk_engine.pipeline` in backend)';
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        message = 'Cannot reach backend server at http://localhost:8000. Is the FastAPI service running?';
      }
      
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFunc]);

  useEffect(() => {
    if (immediate) {
      execute();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, statusCode, refetch: execute, setData };
};
