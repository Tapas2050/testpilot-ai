import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import ScreenshotViewer from '../components/ScreenshotViewer';
import { api } from '../api/client';

describe('ScreenshotViewer Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem('testpilot_token', 'test-auth-token');
    const mockCreate = vi.fn(() => 'blob:http://localhost/test-blob-url');
    const mockRevoke = vi.fn();
    global.URL.createObjectURL = mockCreate;
    global.URL.revokeObjectURL = mockRevoke;
    window.URL.createObjectURL = mockCreate;
    window.URL.revokeObjectURL = mockRevoke;
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders clean fallback when no screenshot path is provided with reason', () => {
    render(
      <ScreenshotViewer
        screenshotPath={null}
        reason="screenshot not captured: selector timed out"
      />
    );
    expect(screen.getByText('No screenshot was captured for this test')).toBeInTheDocument();
    expect(screen.getByText('screenshot not captured: selector timed out')).toBeInTheDocument();
  });

  it('renders default message when no screenshot path and no reason provided', () => {
    render(<ScreenshotViewer screenshotPath={null} />);
    expect(screen.getByText('No screenshot was captured for this test')).toBeInTheDocument();
  });

  it('shows loading state while fetching image', async () => {
    let resolveBlob;
    vi.spyOn(api.runs, 'fetchScreenshotBlob').mockImplementation(() => new Promise((resolve) => {
      resolveBlob = resolve;
    }));

    render(<ScreenshotViewer screenshotPath="screenshots/run-123/tc_1.png" />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();

    const mockBlob = new Blob(['fake png content'], { type: 'image/png' });
    resolveBlob(mockBlob);

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    });
  });

  it('renders image thumbnail and modal on click after successful fetch', async () => {
    const mockBlob = new Blob(['valid png bytes'], { type: 'image/png' });
    vi.spyOn(api.runs, 'fetchScreenshotBlob').mockResolvedValue(mockBlob);

    render(<ScreenshotViewer screenshotPath="screenshots/run-123/tc_1.png" caption="Test Step Final" />);

    // Wait for image thumbnail
    const img = await screen.findByAltText('Test Step Final');
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute('src', 'blob:http://localhost/test-blob-url');

    // Click to open modal
    fireEvent.click(img);
    expect(screen.getByTestId('screenshot-full')).toBeInTheDocument();

    // Close modal
    const closeBtn = screen.getByText('✕');
    fireEvent.click(closeBtn);
    await waitFor(() => {
      expect(screen.queryByTestId('screenshot-full')).not.toBeInTheDocument();
    });
  });

  it('displays fallback message when fetch returns 404 or fails', async () => {
    vi.spyOn(api.runs, 'fetchScreenshotBlob').mockRejectedValue(new Error('Failed to load screenshot'));

    render(
      <ScreenshotViewer
        screenshotPath="screenshots/run-123/missing.png"
        reason="file deleted"
      />
    );

    const fallbackMsg = await screen.findByText('No screenshot was captured for this test');
    expect(fallbackMsg).toBeInTheDocument();
    expect(screen.getByText('file deleted')).toBeInTheDocument();
  });
});
