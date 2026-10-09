/**
 * API client module for interacting with TestPilot AI backend endpoints.
 */

const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request(endpoint, options = {}) {
  const token = sessionStorage.getItem('testpilot_token') || localStorage.getItem('testpilot_token');
  
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const config = {
    ...options,
    headers,
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    let errorMsg = 'An unexpected error occurred';
    if (data?.detail) {
      if (typeof data.detail === 'string') {
        errorMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map(d => d.msg || `${d.loc?.join('.')}: invalid`).join(', ');
      }
    }
    throw new ApiError(errorMsg, response.status, data);
  }

  return data;
}

export const api = {
  auth: {
    login: (email, password) =>
      request('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    register: (email, password) =>
      request('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    me: () => request('/auth/me'),
    logout: () =>
      request('/auth/logout', {
        method: 'POST',
      }),
  },
  projects: {
    list: () => request('/projects'),
    get: (id) => request(`/projects/${id}`),
    create: (data) =>
      request('/projects', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id, data) =>
      request(`/projects/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    delete: (id) =>
      request(`/projects/${id}`, {
        method: 'DELETE',
      }),
    listCredentials: (projectId) => request(`/projects/${projectId}/credentials`),
    addCredential: (projectId, data) =>
      request(`/projects/${projectId}/credentials`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    deleteCredential: (projectId, credentialId) =>
      request(`/projects/${projectId}/credentials/${credentialId}`, {
        method: 'DELETE',
      }),
  },
};

export { ApiError };
