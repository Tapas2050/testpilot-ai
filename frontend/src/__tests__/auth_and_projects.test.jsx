import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { Login } from '../pages/Login';
import { ProjectDialog } from '../components/ProjectDialog';
import { CredentialDialog } from '../components/CredentialDialog';
import { Dashboard } from '../pages/Dashboard';
import { ProjectPage } from '../pages/ProjectPage';
import { api } from '../api/client';

// Mock the API client
vi.mock('../api/client', () => ({
  api: {
    auth: {
      login: vi.fn(),
      register: vi.fn(),
      me: vi.fn(),
      logout: vi.fn(),
    },
    projects: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      listCredentials: vi.fn(),
      addCredential: vi.fn(),
      deleteCredential: vi.fn(),
    },
    documents: {
      list: vi.fn(),
      upload: vi.fn(),
      delete: vi.fn(),
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

describe('Phase 4: Frontend Auth and Project Shell Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
  });

  // T4.1 Protected route redirects when logged out
  it('T4.1 Protected route redirects to /login when unauthenticated', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page Mock</div>} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <div>Secret Dashboard</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Login Page Mock')).toBeInTheDocument();
      expect(screen.queryByText('Secret Dashboard')).not.toBeInTheDocument();
    });
  });

  // T4.2 Login form shows inline errors
  it('T4.2 Login form shows inline errors on invalid submission or failed login', async () => {
    const errorMsg = 'Incorrect email or password.';
    api.auth.login.mockRejectedValueOnce(new Error(errorMsg));

    render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>
    );

    const emailInput = screen.getByLabelText(/Email/i);
    const passwordInput = screen.getByLabelText(/Password/i);
    const submitBtn = screen.getByRole('button', { name: /Sign in/i });

    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'wrongpassword' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });
  });

  // T4.3 Project dialog validation
  it('T4.3 ProjectDialog validates required fields and target URL format', async () => {
    const handleSubmit = vi.fn();
    const handleClose = vi.fn();

    render(
      <ProjectDialog
        isOpen={true}
        onClose={handleClose}
        onSubmit={handleSubmit}
      />
    );

    const submitBtn = screen.getByTestId('project-submit-btn');

    // 1. Submit empty form
    fireEvent.click(submitBtn);
    expect(screen.getByText(/Project name is required/i)).toBeInTheDocument();
    expect(screen.getByText(/Target URL is required/i)).toBeInTheDocument();
    expect(handleSubmit).not.toHaveBeenCalled();

    // 2. Invalid URL
    const nameInput = screen.getByLabelText(/Project Name/i);
    const urlInput = screen.getByLabelText(/Target Application URL/i);

    fireEvent.change(nameInput, { target: { value: 'Test Project' } });
    fireEvent.change(urlInput, { target: { value: 'invalid-url' } });
    fireEvent.click(submitBtn);

    expect(screen.getByText(/URL must begin with http:\/\/ or https:\/\//i)).toBeInTheDocument();
    expect(handleSubmit).not.toHaveBeenCalled();

    // 3. Valid URL
    fireEvent.change(urlInput, { target: { value: 'http://localhost:3000' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledWith({
        name: 'Test Project',
        description: null,
        target_url: 'http://localhost:3000',
      });
    });
  });

  // T4.4 Credential dialog validation
  it('T4.4 CredentialDialog validates required fields', async () => {
    const handleSubmit = vi.fn();
    const handleClose = vi.fn();

    render(
      <CredentialDialog
        isOpen={true}
        onClose={handleClose}
        onSubmit={handleSubmit}
      />
    );

    const submitBtn = screen.getByTestId('cred-submit-btn');

    // Submit empty form
    fireEvent.click(submitBtn);
    expect(screen.getByText(/Username and password are required/i)).toBeInTheDocument();
    expect(handleSubmit).not.toHaveBeenCalled();

    // Fill valid data
    const roleInput = screen.getByLabelText(/Role Label/i);
    const userInput = screen.getByLabelText(/Username or Email/i);
    const passInput = screen.getByLabelText(/Password/i);

    fireEvent.change(roleInput, { target: { value: 'admin' } });
    fireEvent.change(userInput, { target: { value: 'admin@example.com' } });
    fireEvent.change(passInput, { target: { value: 'supersecret' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleSubmit).toHaveBeenCalledWith({
        role_label: 'admin',
        username: 'admin@example.com',
        password: 'supersecret',
      });
    });
  });

  // Dashboard component tests
  it('renders Dashboard with empty state when no projects exist', async () => {
    api.projects.list.mockResolvedValueOnce([]);

    render(
      <MemoryRouter>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No projects yet. Create one to start testing.')).toBeInTheDocument();
    });
  });

  // ProjectPage empty documents state and disabled Start Run
  it('renders ProjectPage with disabled Start Run button when no documents exist', async () => {
    api.projects.get.mockResolvedValueOnce({
      id: 'proj-123',
      name: 'SupportDesk Test',
      description: 'SupportDesk application testing',
      target_url: 'http://localhost:3000',
    });
    api.projects.listCredentials.mockResolvedValueOnce([]);
    api.documents.list.mockResolvedValueOnce([]);

    render(
      <MemoryRouter initialEntries={['/projects/proj-123']}>
        <AuthProvider>
          <Routes>
            <Route path="/projects/:id" element={<ProjectPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'SupportDesk Test' })).toBeInTheDocument();
      expect(screen.getByText(/Upload your requirements so the agent knows what to test/i)).toBeInTheDocument();
      const startBtn = screen.getByTestId('start-run-btn');
      expect(startBtn).toBeDisabled();
    });
  });

  // ProjectPage with documents enables Start Run button
  it('renders ProjectPage with documents and enables Start Run button', async () => {
    api.projects.get.mockResolvedValueOnce({
      id: 'proj-123',
      name: 'SupportDesk Test',
      description: 'SupportDesk application testing',
      target_url: 'http://localhost:3000',
    });
    api.projects.listCredentials.mockResolvedValueOnce([]);
    api.documents.list.mockResolvedValueOnce([
      {
        id: 'doc-1',
        original_name: 'requirements.pdf',
        file_type: 'pdf',
        size_bytes: 10240,
        extraction_status: 'SUCCESS',
      },
    ]);

    render(
      <MemoryRouter initialEntries={['/projects/proj-123']}>
        <AuthProvider>
          <Routes>
            <Route path="/projects/:id" element={<ProjectPage />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('requirements.pdf')).toBeInTheDocument();
      expect(screen.getByText('SUCCESS')).toBeInTheDocument();
      const startBtn = screen.getByTestId('start-run-btn');
      expect(startBtn).not.toBeDisabled();
    });
  });
});
