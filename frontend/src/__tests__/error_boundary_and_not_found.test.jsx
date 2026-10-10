import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { NotFoundPage } from '../pages/NotFoundPage';

function ThrowingComponent({ message = 'Simulated crash' }) {
  throw new Error(message);
}

describe('ErrorBoundary and NotFoundPage Tests', () => {
  it('catches runtime rendering errors and displays readable error message and back button', () => {
    // Suppress console.error in test output for intentional throw
    const originalError = console.error;
    console.error = vi.fn();

    render(
      <ErrorBoundary>
        <ThrowingComponent message="Cannot read properties of undefined (reading 'bg')" />
      </ErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeDefined();
    expect(screen.getByText('Application Error')).toBeDefined();
    expect(screen.getByText("Cannot read properties of undefined (reading 'bg')")).toBeDefined();
    expect(screen.getByText('← Back to Project')).toBeDefined();

    console.error = originalError;
  });

  it('renders NotFoundPage with 404 message and link to dashboard', () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    expect(screen.getByText('404')).toBeDefined();
    expect(screen.getByText('Page Not Found')).toBeDefined();
    const link = screen.getByText('← Back to Dashboard');
    expect(link).toBeDefined();
    expect(link.getAttribute('href')).toBe('/');
  });
});
