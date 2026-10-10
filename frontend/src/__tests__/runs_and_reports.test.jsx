import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { useRunStatus } from '../hooks/useRunStatus';
import { TestRunPage } from '../pages/TestRunPage';
import { ReportPage } from '../pages/ReportPage';
import { ProjectPage } from '../pages/ProjectPage';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    auth: {
      me: vi.fn().mockResolvedValue({ id: 'user-1', email: 'test@example.com' }),
      logout: vi.fn(),
    },
    projects: {
      get: vi.fn(),
      listCredentials: vi.fn().mockResolvedValue([]),
      list: vi.fn().mockResolvedValue([]),
      update: vi.fn(),
      delete: vi.fn(),
      addCredential: vi.fn(),
      deleteCredential: vi.fn(),
    },
    documents: {
      list: vi.fn().mockResolvedValue([]),
      upload: vi.fn(),
      delete: vi.fn(),
    },
    runs: {
      create: vi.fn(),
      list: vi.fn().mockResolvedValue([]),
      get: vi.fn(),
      cancel: vi.fn(),
      report: vi.fn(),
      fetchScreenshotBlob: vi.fn(),
    },
  },
  ApiError: class ApiError extends Error {
    constructor(msg, status, data) {
      super(msg);
      this.status = status;
      this.data = data;
    }
  },
}));

describe('Phase 12: Runs and Reports Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
    sessionStorage.setItem('testpilot_token', 'mock-token');
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // T12.1: useRunStatus polls and stops on terminal states
  it('T12.1 useRunStatus polls and stops on terminal states', async () => {
    vi.useFakeTimers();

    // 1st call: RUNNING, 2nd call: RUNNING, 3rd call: COMPLETED
    api.runs.get
      .mockResolvedValueOnce({
        id: 'run-123',
        status: 'RUNNING',
        agent_stage: 'EXECUTING',
        test_cases: [],
        results: [],
      })
      .mockResolvedValueOnce({
        id: 'run-123',
        status: 'RUNNING',
        agent_stage: 'ANALYZING',
        test_cases: [],
        results: [],
      })
      .mockResolvedValueOnce({
        id: 'run-123',
        status: 'COMPLETED',
        agent_stage: 'COMPLETED',
        test_cases: [],
        results: [],
      });

    const { result } = renderHook(() => useRunStatus('run-123', { pollInterval: 2000 }));

    // Initial fetch
    await act(async () => {
      await Promise.resolve();
    });

    expect(api.runs.get).toHaveBeenCalledTimes(1);
    expect(result.current.run?.status).toBe('RUNNING');
    expect(result.current.isTerminal).toBe(false);

    // Fast-forward 2000ms -> 2nd poll
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(api.runs.get).toHaveBeenCalledTimes(2);
    expect(result.current.run?.agent_stage).toBe('ANALYZING');

    // Fast-forward another 2000ms -> 3rd poll returns COMPLETED
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(api.runs.get).toHaveBeenCalledTimes(3);
    expect(result.current.run?.status).toBe('COMPLETED');
    expect(result.current.isTerminal).toBe(true);

    // Advance more time: polling must NOT trigger again
    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });

    expect(api.runs.get).toHaveBeenCalledTimes(3);
  });

  // T12.2: Banners for FAILED and CANCELLED
  it('T12.2 TestRunPage renders FAILED banner with stage/error and CANCELLED banner', async () => {
    // Test FAILED banner
    api.runs.get.mockResolvedValueOnce({
      id: 'run-fail-1',
      project_id: 'proj-1',
      status: 'FAILED',
      agent_stage: 'EXECUTING',
      error_message: 'Browser crashed unexpectedly',
      test_cases: [
        {
          id: 'tc-1',
          test_key: 'TEST-001',
          title: 'Verify Login',
          priority: 'HIGH',
          source_requirement: 'SEC-1',
          steps: ['Step 1: Navigate to login'],
        },
      ],
      results: [],
    });

    const { unmount } = render(
      <MemoryRouter initialEntries={['/runs/run-fail-1']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Run Failed')).toBeDefined();
      expect(screen.getByText(/Browser crashed unexpectedly/)).toBeDefined();
    });

    unmount();

    // Test CANCELLED banner
    api.runs.get.mockResolvedValueOnce({
      id: 'run-cancel-1',
      project_id: 'proj-1',
      status: 'CANCELLED',
      agent_stage: 'EXECUTING',
      test_cases: [],
      results: [],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-cancel-1']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Run Cancelled')).toBeDefined();
      expect(screen.getByText(/cancelled by the user/)).toBeDefined();
    });
  });

  // T12.3: Report renders stats, failures and screenshots
  it('T12.3 ReportPage renders stats, severity breakdown, failure details, and evidence', async () => {
    api.runs.fetchScreenshotBlob.mockResolvedValue(new Blob(['fake-img'], { type: 'image/png' }));
    global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-screenshot-url');

    api.runs.report.mockResolvedValueOnce({
      total_tests: 5,
      passed_tests: 4,
      failed_tests: 1,
      pass_percentage: 80.0,
      summary: '4 out of 5 tests passed. One regression observed in permission logic.',
      classification_breakdown: { PRODUCT_BUG: 1 },
      severity_breakdown: { HIGH: 1 },
      test_cases: [
        { id: 'tc-1', test_key: 'TEST-001', title: 'Agent Cannot Delete Ticket' },
      ],
      results: [
        {
          id: 'res-1',
          test_case_id: 'tc-1',
          status: 'FAILED',
          evidence_paths: ['storage/screenshots/tc_1_delete_bug.png'],
        },
      ],
      failures: [
        {
          id: 'fail-1',
          test_result_id: 'res-1',
          classification: 'PRODUCT_BUG',
          severity: 'HIGH',
          confidence: 0.95,
          expected_behavior: 'Non-admin receives 403 Forbidden',
          observed_behavior: 'Delete button was active and delete succeeded',
          explanation: 'The backend endpoint omitted user role verification.',
          suggested_action: 'Add role == admin authorization check.',
        },
      ],
      generated_at: new Date().toISOString(),
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-rep-1/report']}>
        <Routes>
          <Route path="/runs/:id/report" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      // Check stat tiles
      expect(screen.getByTestId('stat-total').textContent).toContain('5');
      expect(screen.getByTestId('stat-passed').textContent).toContain('4');
      expect(screen.getByTestId('stat-failed').textContent).toContain('1');
      expect(screen.getByTestId('stat-pass-rate').textContent).toContain('80%');

      // Check AI summary
      expect(screen.getByTestId('ai-summary').textContent).toContain('4 out of 5 tests passed');

      // Check failure details
      expect(screen.getByText('PRODUCT_BUG')).toBeDefined();
      expect(screen.getByText('HIGH')).toBeDefined();
      expect(screen.getByText('Non-admin receives 403 Forbidden')).toBeDefined();
      expect(screen.getByText('Delete button was active and delete succeeded')).toBeDefined();
      expect(screen.getByText(/The backend endpoint omitted user role verification/)).toBeDefined();

      // Check screenshot thumbnail
      expect(screen.getByTestId('screenshot-thumbnail')).toBeDefined();
    });
  });

  // T12.4: Start Test Run button disabled until documents exist
  it('T12.4 ProjectPage Start Run button disabled when no documents, enabled when documents exist', async () => {
    api.projects.get.mockResolvedValueOnce({
      id: 'proj-1',
      name: 'SupportDesk Target',
      target_url: 'http://localhost:8001',
    });
    api.documents.list.mockResolvedValueOnce([]); // 0 documents
    api.runs.list.mockResolvedValueOnce([]);

    const { unmount } = render(
      <MemoryRouter initialEntries={['/projects/proj-1']}>
        <AuthProvider>
          <Routes>
            <Route path="/projects/:id" element={<ProjectPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      const startBtn = screen.getByTestId('start-run-btn');
      expect(startBtn.disabled).toBe(true);
    });

    unmount();

    // Now with documents
    api.projects.get.mockResolvedValueOnce({
      id: 'proj-1',
      name: 'SupportDesk Target',
      target_url: 'http://localhost:8001',
    });
    api.documents.list.mockResolvedValueOnce([
      { id: 'doc-1', original_name: 'requirements.md', file_type: 'md', size_bytes: 1200 },
    ]);
    api.runs.list.mockResolvedValueOnce([]);
    api.runs.create.mockResolvedValueOnce({ id: 'run-new-999', project_id: 'proj-1' });

    render(
      <MemoryRouter initialEntries={['/projects/proj-1']}>
        <AuthProvider>
          <Routes>
            <Route path="/projects/:id" element={<ProjectPage />} />
            <Route path="/projects/:projectId/runs/:id" element={<div>Run Detail Screen</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      const startBtn = screen.getByTestId('start-run-btn');
      expect(startBtn.disabled).toBe(false);
    });

    // Click Start Run
    const startBtn = screen.getByTestId('start-run-btn');
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(api.runs.create).toHaveBeenCalledWith('proj-1');
      expect(screen.getByText('Run Detail Screen')).toBeDefined();
    });
  });

  it('renders TestRunPage cleanly for every status including unknown statuses without throwing', async () => {
    const statusesToTest = [
      'QUEUED',
      'PLANNING',
      'EXECUTING',
      'ANALYZING',
      'REPORTING',
      'COMPLETED',
      'FAILED',
      'CANCELLED',
      'UNKNOWN_STATUS_XYZ',
    ];

    for (const status of statusesToTest) {
      api.runs.get.mockResolvedValueOnce({
        id: `run-${status}`,
        project_id: 'proj-1',
        status,
        agent_stage: status,
        test_cases: [
          { id: 'tc-1', test_key: 'TC-01', title: 'Login test', requirement_id: 'REQ-1' },
        ],
        results: [
          { id: 'res-1', test_case_id: 'tc-1', status: 'RUNNING', steps: [] },
        ],
      });

      const { unmount } = render(
        <MemoryRouter initialEntries={[`/runs/run-${status}`]}>
          <Routes>
            <Route path="/runs/:id" element={<TestRunPage />} />
          </Routes>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getAllByText(status).length).toBeGreaterThan(0);
      });

      unmount();
    }
  });

  it('renders TestRunPage when run is QUEUED with zero test cases and no report', async () => {
    api.runs.get.mockResolvedValueOnce({
      id: 'run-queued-empty',
      project_id: 'proj-1',
      status: 'QUEUED',
      agent_stage: 'INITIALIZING',
      test_cases: [],
      results: [],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-queued-empty']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('QUEUED')).toBeDefined();
      expect(screen.getByText('Planning tests from your requirements...')).toBeDefined();
    });
  });

  it('renders ReportPage with unknown severity without throwing', async () => {
    api.runs.report.mockResolvedValueOnce({
      id: 'rep-unknown-sev',
      run_id: 'run-rep-unk',
      total_tests: 1,
      passed_tests: 0,
      failed_tests: 1,
      pass_percentage: 0,
      summary: 'Test failure with unknown severity',
      severity_breakdown: { UNKNOWN_SEV: 1 },
      classification_breakdown: { UNKNOWN_CLS: 1 },
      failures: [
        {
          id: 'fail-1',
          test_result_id: 'res-1',
          severity: 'UNKNOWN_SEV',
          classification: 'UNKNOWN_CLS',
          expected: 'Page loads',
          observed: 'Error 500',
          explanation: 'Unexpected backend error',
          suggested_action: 'Fix server',
        },
      ],
      test_cases: [{ id: 'tc-1', test_key: 'TC-1', title: 'Failing test' }],
      results: [{ id: 'res-1', test_case_id: 'tc-1', status: 'FAILED' }],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-rep-unk/report']}>
        <Routes>
          <Route path="/runs/:id/report" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test failure with unknown severity')).toBeDefined();
      expect(screen.getByText('UNKNOWN_SEV: 1')).toBeDefined();
      expect(screen.getByText('UNKNOWN_SEV')).toBeDefined();
    });
  });
});
