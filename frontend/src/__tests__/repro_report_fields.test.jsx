import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ReportPage } from '../pages/ReportPage';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    runs: {
      report: vi.fn(),
      fetchScreenshotBlob: vi.fn(),
    },
  },
}));

describe('ReportPage Failure Cards Field Mapping Reproduction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders expected and observed behavior from f.expected and f.observed fields', async () => {
    api.runs.report.mockResolvedValueOnce({
      total_tests: 1,
      passed_tests: 0,
      failed_tests: 1,
      pass_percentage: 0,
      summary: '1 failure detected.',
      severity_breakdown: { HIGH: 1 },
      classification_breakdown: { PRODUCT_BUG: 1 },
      failures: [
        {
          id: 'fail-1',
          test_case_id: 'tc-1',
          title: 'Ticket Priority Integrity',
          classification: 'PRODUCT_BUG',
          severity: 'HIGH',
          confidence: 0.95,
          expected: 'Ticket priority selected as High should be stored as High.',
          observed: 'Ticket priority was stored as Low.',
          explanation: 'Backend persisted Low instead of High.',
          suggested_action: 'Fix priority persistence logic in backend.',
          screenshot_path: 'screenshots/run-1/tc-1.png',
        },
      ],
      test_cases: [{ id: 'tc-1', test_key: 'TC-1', title: 'Ticket Priority Integrity' }],
      results: [{ id: 'res-1', test_case_id: 'tc-1', status: 'FAILED' }],
      generated_at: new Date().toISOString(),
    });

    render(
      <MemoryRouter initialEntries={['/runs/run-1/report']}>
        <Routes>
          <Route path="/runs/:id/report" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Ticket priority selected as High should be stored as High.')).toBeInTheDocument();
      expect(screen.getByText('Ticket priority was stored as Low.')).toBeInTheDocument();
    });
  });
});
