import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useRunStatus } from '../hooks/useRunStatus';
import { api } from '../api/client';

describe('useRunStatus Hook Live Progression and Sequence Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('progresses through a sequence of run stages and stops at COMPLETED', async () => {
    const responses = [
      { id: 'run-1', status: 'QUEUED', stage: 'QUEUED', updated_at: '2026-10-13T10:00:00Z' },
      { id: 'run-1', status: 'PLANNING', stage: 'PLANNING', updated_at: '2026-10-13T10:00:02Z' },
      { id: 'run-1', status: 'EXECUTING', stage: 'EXECUTING', updated_at: '2026-10-13T10:00:04Z' },
      { id: 'run-1', status: 'COMPLETED', stage: 'COMPLETED', updated_at: '2026-10-13T10:00:06Z' },
    ];

    let callCount = 0;
    vi.spyOn(api.runs, 'get').mockImplementation(async () => {
      const resp = responses[Math.min(callCount, responses.length - 1)];
      callCount += 1;
      return resp;
    });

    const { result } = renderHook(() => useRunStatus('run-1', { pollInterval: 500 }));

    // 1. Initial call
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.run?.status).toBe('QUEUED');

    // 2. Poll 1 -> PLANNING
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(result.current.run?.status).toBe('PLANNING');

    // 3. Poll 2 -> EXECUTING
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(result.current.run?.status).toBe('EXECUTING');

    // 4. Poll 3 -> COMPLETED
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(result.current.run?.status).toBe('COMPLETED');
    expect(result.current.isTerminal).toBe(true);

    const callsAtCompletion = callCount;
    // Further timer advance should NOT poll anymore
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(callCount).toBe(callsAtCompletion);
  });
});
