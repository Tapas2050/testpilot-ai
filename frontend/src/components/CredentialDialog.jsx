import React, { useState } from 'react';

export function CredentialDialog({ isOpen, onClose, onSubmit }) {
  const [roleLabel, setRoleLabel] = useState('admin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password) {
      setError('Username and password are required');
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit({
        role_label: roleLabel.trim(),
        username: username.trim(),
        password,
      });
      setUsername('');
      setPassword('');
      setRoleLabel('admin');
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save credential');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="cred-dialog-title">
      <div className="modal-content">
        <div className="modal-header">
          <h2 id="cred-dialog-title" style={{ fontSize: '16px' }}>Add Test Credential</h2>
          <button onClick={onClose} aria-label="Close" style={{ fontSize: '18px', color: 'var(--text-secondary)' }}>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="badge badge-fail" style={{ width: '100%', padding: '8px 12px', marginBottom: '16px', borderRadius: '4px' }}>
                {error}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="role-label" className="form-label">Role Label *</label>
              <select
                id="role-label"
                className="form-select"
                value={roleLabel}
                onChange={(e) => setRoleLabel(e.target.value)}
              >
                <option value="admin">admin</option>
                <option value="agent">agent / support</option>
                <option value="user">standard user</option>
                <option value="custom">other</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="cred-username" className="form-label">Username or Email *</label>
              <input
                id="cred-username"
                className="form-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. admin@supportdesk.local"
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label htmlFor="cred-password" className="form-label">Password *</label>
              <input
                id="cred-password"
                type="password"
                className="form-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Plaintext password (encrypted at rest)"
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" onClick={onClose} className="btn btn-secondary" disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" data-testid="cred-submit-btn" disabled={submitting}>
              {submitting ? 'Encrypting...' : 'Save Credential'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
