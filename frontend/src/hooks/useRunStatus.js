import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api/client';

export const TERMINAL_STATES = ['COMPLETED', 'FAILED', 'CANCELLED'];

export function useRunStatus(runId, options = {}) {
  const { pollInterval = 2000, enabled = true } = options;

  const [run, setRun] = useState(null);
  const [testCases, setTestCases] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  const timerRef = useRef(null);
  const isMountedRef = useRef(true);

  const fetchRun = useCallback(async () => {
    if (!runId) return;
    try {
      const data = await api.runs.get(runId);
      if (!isMountedRef.current) return;
      setRun(data);
      if (data.test_cases) setTestCases(data.test_cases);
      if (data.results) setResults(data.results);
      setError(null);
      return data;
    } catch (err) {
      if (!isMountedRef.current) return;
      setError(err.message || 'Failed to fetch test run details');
      return null;
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [runId]);

  const cancelRun = useCallback(async () => {
    if (!runId) return;
    try {
      setCancelling(true);
      await api.runs.cancel(runId);
      await fetchRun();
    } catch (err) {
      setError(err.message || 'Failed to cancel test run');
    } finally {
      if (isMountedRef.current) {
        setCancelling(false);
      }
    }
  }, [runId, fetchRun]);

  useEffect(() => {
    isMountedRef.current = true;
    if (!runId || !enabled) {
      setLoading(false);
      return;
    }

    let active = true;

    async function poll() {
      const currentRun = await fetchRun();
      if (!active) return;

      if (currentRun && TERMINAL_STATES.includes(currentRun.status)) {
        // Terminal state reached: stop polling
        return;
      }

      timerRef.current = setTimeout(poll, pollInterval);
    }

    poll();

    return () => {
      active = false;
      isMountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [runId, pollInterval, enabled, fetchRun]);

  return {
    run,
    testCases,
    results,
    loading,
    error,
    cancelling,
    cancelRun,
    refetch: fetchRun,
    isTerminal: run ? TERMINAL_STATES.includes(run.status) : false,
  };
}
