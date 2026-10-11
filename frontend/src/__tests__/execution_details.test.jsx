import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { TestRunPage } from '../pages/TestRunPage';
import { ReportPage } from '../pages/ReportPage';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    runs: {
      get: vi.fn(),
      report: vi.fn(),
      fetchScreenshotBlob: vi.fn().mockResolvedValue(new Blob(['fake-img'], { type: 'image/png' })),
    },
  },
}));

describe('Part 2: Execution Details & Step Timeline Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('renders expanded test row with steps, selector, observation, duration, and evidence quote', async () => {
    api.runs.get.mockResolvedValue({
      id: 'run-exec-1',
      project_id: 'proj-1',
      status: 'COMPLETED',
      created_at: new Date().toISOString(),
      started_at: new Date(Date.now() - 5000).toISOString(),
      completed_at: new Date().toISOString(),
      total_tests: 1,
      completed_tests: 1,
      passed_tests: 1,
      failed_tests: 0,
      test_cases: [
        {
          id: 'tc-1',
          title: 'Ticket Creation Flow',
          test_key: 'TC-1',
          status: 'PASSED',
          source_requirement: 'REQ-TC-01',
          checks: [
            { check_id: 'chk-1', description: 'Ticket is created with ID', source_requirement: 'REQ-TC-01' },
          ],
          check_results: [
            { check_id: 'chk-1', result: 'PASSED', evidence: 'Ticket #101 created successfully' },
          ],
          duration_seconds: 4.2,
          screenshot_path: 'screenshots/run-exec-1/tc-1.png',
          evidence: 'Ticket #101 created successfully',
          final_observation: 'Ticket form submitted and ticket appears in list',
          steps: [
            {
              step: 1,
              action: 'navigate',
              url: 'http://localhost:8001/tickets/new',
              observation: 'Navigated to new ticket page',
            },
            {
              step: 2,
              action: 'fill',
              selector: '#title',
              value: 'Bug report',
              observation: 'Filled title input',
            },
            {
              step: 3,
              action: 'click',
              selector: 'button[type="submit"]',
              observation: 'Clicked submit button',
            },
          ],
        },
      ],
      results: [
        {
          id: 'res-1',
          test_case_id: 'tc-1',
          status: 'PASSED',
          duration_seconds: 4.2,
          screenshot_path: 'screenshots/run-exec-1/tc-1.png',
          evidence: 'Ticket #101 created successfully',
          final_observation: 'Ticket form submitted and ticket appears in list',
          steps: [
            {
              step: 1,
              action: 'navigate',
              url: 'http://localhost:8001/tickets/new',
              observation: 'Navigated to new ticket page',
            },
            {
              step: 2,
              action: 'fill',
              selector: '#title',
              value: 'Bug report',
              observation: 'Filled title input',
            },
            {
              step: 3,
              action: 'click',
              selector: 'button[type="submit"]',
              observation: 'Clicked submit button',
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-exec-1']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Ticket Creation Flow')).toBeInTheDocument();
    });

    // Expand the test row
    fireEvent.click(screen.getByText('Ticket Creation Flow'));

    // Check checks & verdicts
    expect(screen.getByText('Requirement Checks:')).toBeInTheDocument();
    expect(screen.getByText('Ticket is created with ID')).toBeInTheDocument();

    // Check duration and observations
    expect(screen.getByText(/Duration: 4.2s/i)).toBeInTheDocument();
    expect(screen.getByText(/Ticket form submitted and ticket appears in list/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Ticket #101 created successfully/i).length).toBeGreaterThan(0);

    // Check step timeline items
    expect(screen.getByText(/Navigated to new ticket page/i)).toBeInTheDocument();
    expect(screen.getByText(/Filled title input/i)).toBeInTheDocument();
    expect(screen.getByText(/Clicked submit button/i)).toBeInTheDocument();
    expect(screen.getByText('http://localhost:8001/tickets/new')).toBeInTheDocument();
    expect(screen.getByText('#title')).toBeInTheDocument();
  });

  it('renders expanded test row with friendly "no steps recorded" message when steps are empty', async () => {
    api.runs.get.mockResolvedValue({
      id: 'run-exec-2',
      project_id: 'proj-1',
      status: 'FAILED',
      created_at: new Date().toISOString(),
      started_at: new Date(Date.now() - 3000).toISOString(),
      completed_at: new Date().toISOString(),
      total_tests: 1,
      completed_tests: 0,
      test_cases: [
        {
          id: 'tc-empty',
          title: 'Unexecuted Scenario',
          test_key: 'TC-2',
          status: 'NOT_RUN',
          error_message: 'Not executed: run stopped due to preflight failure',
          steps: [],
        },
      ],
      results: [],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-exec-2']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Unexecuted Scenario')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Unexecuted Scenario'));

    await waitFor(() => {
      const emptyMsg = screen.getByTestId('no-steps-message');
      expect(emptyMsg).toBeInTheDocument();
      expect(emptyMsg.textContent).toContain('No steps recorded for this test');
      expect(emptyMsg.textContent).toContain('preflight failure');
    });
  });

  it('handles unknown action name gracefully with default fallback styling', async () => {
    api.runs.get.mockResolvedValue({
      id: 'run-exec-3',
      project_id: 'proj-1',
      status: 'COMPLETED',
      created_at: new Date().toISOString(),
      test_cases: [
        {
          id: 'tc-custom',
          title: 'Custom Action Scenario',
          test_key: 'TC-3',
          status: 'PASSED',
          steps: [
            {
              step: 1,
              action: 'custom_exotic_action',
              selector: '#special-elem',
              observation: 'Executed custom action smoothly',
            },
          ],
        },
      ],
      results: [
        {
          id: 'res-custom',
          test_case_id: 'tc-custom',
          status: 'PASSED',
          steps: [
            {
              step: 1,
              action: 'custom_exotic_action',
              selector: '#special-elem',
              observation: 'Executed custom action smoothly',
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-exec-3']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Custom Action Scenario')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Custom Action Scenario'));

    await waitFor(() => {
      expect(screen.getByText('custom_exotic_action')).toBeInTheDocument();
      expect(screen.getByText('#special-elem')).toBeInTheDocument();
      expect(screen.getByText(/Executed custom action smoothly/i)).toBeInTheDocument();
    });
  });

  it('renders execution details on ReportPage when failure card is expanded', async () => {
    api.runs.report.mockResolvedValue({
      total_tests: 1,
      passed_tests: 0,
      failed_tests: 1,
      pass_percentage: 0.0,
      summary: '1 test failed',
      classification_breakdown: { PRODUCT_BUG: 1 },
      severity_breakdown: { HIGH: 1 },
      failures: [
        {
          id: 'fail-1',
          test_case_id: 'tc-fail',
          classification: 'PRODUCT_BUG',
          severity: 'HIGH',
          expected: 'Expected non-admin receives 403',
          observed: 'Observed non-admin was able to delete',
          explanation: 'Permission check omitted in controller',
          suggested_action: 'Add RBAC guard',
          screenshot_path: 'screenshots/run-exec-4/fail-1.png',
        },
      ],
      test_cases: [
        {
          id: 'tc-fail',
          title: 'Delete Permission Test',
          test_key: 'TC-4',
          status: 'FAILED',
          checks: [{ check_id: 'chk-del', description: 'Agent cannot delete tickets' }],
        },
      ],
      results: [
        {
          id: 'res-fail',
          test_case_id: 'tc-fail',
          status: 'FAILED',
          duration_seconds: 3.5,
          screenshot_path: 'screenshots/run-exec-4/fail-1.png',
          evidence: 'Delete button was visible and active',
          final_observation: 'Ticket was deleted without 403 error',
          steps: [
            {
              step: 1,
              action: 'click',
              selector: '.delete-btn',
              observation: 'Clicked delete button on ticket row',
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-exec-4/report']}>
        <Routes>
          <Route path="/runs/:id/report" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Expected non-admin receives 403')).toBeInTheDocument();
      expect(screen.getByText('Observed non-admin was able to delete')).toBeInTheDocument();
    });

    // Expand execution details
    fireEvent.click(screen.getByText(/Show Execution Details/i));

    await waitFor(() => {
      expect(screen.getByText(/Ticket was deleted without 403 error/i)).toBeInTheDocument();
      expect(screen.getByText(/Clicked delete button on ticket row/i)).toBeInTheDocument();
      expect(screen.getByText('.delete-btn')).toBeInTheDocument();
    });
  });
});
