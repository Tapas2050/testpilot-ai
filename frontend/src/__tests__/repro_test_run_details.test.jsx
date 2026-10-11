import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { TestRunPage } from '../pages/TestRunPage';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    runs: {
      get: vi.fn(),
      fetchScreenshotBlob: vi.fn(),
    },
  },
}));

describe('TestRunPage Expanded Row Details Reproduction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders step timeline and screenshot thumbnail when row is expanded', async () => {
    api.runs.get.mockResolvedValueOnce({
      id: 'run-1',
      project_id: 'proj-1',
      status: 'COMPLETED',
      agent_stage: 'COMPLETED',
      current_stage: 'COMPLETED',
      total_tests: 1,
      completed_tests: 1,
      passed_tests: 1,
      failed_tests: 0,
      blocked_tests: 0,
      not_run_tests: 0,
      test_cases: [
        {
          id: 'tc-1',
          test_key: 'TC-01',
          title: 'User Authentication and Logout',
          source_requirement: 'REQ-AUTH-01',
          target_role: 'agent',
          status: 'PASSED',
          order_index: 1,
        },
      ],
      results: [
        {
          id: 'res-1',
          test_case_id: 'tc-1',
          status: 'PASSED',
          duration_seconds: 7.91,
          screenshot_path: 'screenshots/run-1/tc-1.png',
          steps: [
            { step: 1, action: 'login', selector: 'form', status: 'ok', observation: 'Logged in as agent' },
            { step: 2, action: 'click', selector: '#logout-btn', status: 'ok', observation: 'Clicked logout' },
            { step: 3, action: 'finish', status: 'PASSED', observation: 'User successfully logged out' },
          ],
        },
      ],
      recent_events: [],
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-1']}>
        <Routes>
          <Route path="/runs/:id" element={<TestRunPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('User Authentication and Logout')).toBeInTheDocument();
    });

    // Expand the test case row
    fireEvent.click(screen.getByText('User Authentication and Logout'));

    // Should display step timeline
    await waitFor(() => {
      expect(screen.getByText(/Logged in as agent/i)).toBeInTheDocument();
    });
  });
});
