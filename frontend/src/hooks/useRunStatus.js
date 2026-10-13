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
  const [lastUpdateSeconds, setLastUpdateSeconds] = useState(0);

  const timerRef = useRef(null);
  const isMountedRef = useRef(true);
  const requestSeqRef = useRef(0);
  const latestTimestampRef = useRef(0);

  const fetchRun = useCallback(async () => {
    if (!runId) return null;
    const currentSeq = ++requestSeqRef.current;
    try {
      const data = await api.runs.get(runId);
      if (!isMountedRef.current) return null;

      // Stale-response ordering: ignore out-of-order responses
      if (currentSeq < requestSeqRef.current) {
        return null;
      }

      if (data?.updated_at) {
        const updateTs = new Date(data.updated_at).getTime();
        if (updateTs < latestTimestampRef.current) {
          // Ignore response with an older updated_at than what we already applied
          return null;
        }
        latestTimestampRef.current = updateTs;
      }

      setRun(data);
      if (data.test_cases) setTestCases(data.test_cases);
      if (data.results) setResults(data.results);
      setError(null);
      return data;
    } catch (err) {
      if (!isMountedRef.current) return null;
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

  // Polling loop
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

  // Counter for seconds since last update / change
  const lastChangeTimeRef = useRef(0);
  const prevSignatureRef = useRef('');

  useEffect(() => {
    if (!lastChangeTimeRef.current) {
      lastChangeTimeRef.current = Date.now();
    }
    if (!run) return;
    const sig = `${run.updated_at || ''}-${run.stage || ''}-${run.status || ''}-${run.current_step || ''}-${run.completed_tests || ''}-${run.tests_done || ''}`;
    if (prevSignatureRef.current !== sig) {
      prevSignatureRef.current = sig;
      lastChangeTimeRef.current = Date.now();
      setLastUpdateSeconds(0);
    }
  }, [run]);

  useEffect(() => {
    const calcSecs = () => {
      const secs = Math.max(0, Math.floor((Date.now() - lastChangeTimeRef.current) / 1000));
      setLastUpdateSeconds(secs);
    };

    const interval = setInterval(calcSecs, 1000);
    return () => clearInterval(interval);
  }, []);

  const isTerminal = run ? TERMINAL_STATES.includes(run.status) : false;
  const isStalled = !isTerminal && lastUpdateSeconds >= 60;

  return {
    run,
    testCases,
    results,
    loading,
    error,
    cancelling,
    cancelRun,
    refetch: fetchRun,
    isTerminal,
    lastUpdateSeconds,
    isStalled,
  };
}
