import React, { useState, useEffect } from 'react';

export function ProjectDialog({ isOpen, onClose, onSubmit, initialData = null }) {
  const [name, setName] = useState('');
  const [targetUrl, setTargetUrl] = useState('');
  const [description, setDescription] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState('');

  useEffect(() => {
    if (initialData) {
      setName(initialData.name || '');
      setTargetUrl(initialData.target_url || '');
      setDescription(initialData.description || '');
    } else {
      setName('');
      setTargetUrl('');
      setDescription('');
    }
    setErrors({});
    setServerError('');
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const validate = () => {
    const errs = {};
    if (!name.trim()) {
      errs.name = 'Project name is required';
    }
    if (!targetUrl.trim()) {
      errs.targetUrl = 'Target URL is required';
    } else if (!/^https?:\/\//i.test(targetUrl.trim())) {
      errs.targetUrl = 'URL must begin with http:// or https://';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    if (!validate()) return;

    setSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        target_url: targetUrl.trim(),
        description: description.trim() || null,
      });
      onClose();
    } catch (err) {
      setServerError(err.message || 'Failed to save project');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
      <div className="modal-content">
        <div className="modal-header">
          <h2 id="dialog-title" style={{ fontSize: '16px' }}>
            {initialData ? 'Edit Project' : 'New Project'}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{ fontSize: '18px', color: 'var(--text-secondary)' }}
          >
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {serverError && (
              <div className="badge badge-fail" style={{ width: '100%', padding: '8px 12px', marginBottom: '16px', borderRadius: '4px' }}>
                {serverError}
              </div>
            )}

            <div className="form-group">
              <label htmlFor="project-name" className="form-label">Project Name *</label>
              <input
                id="project-name"
                data-testid="project-name-input"
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. SupportDesk App"
              />
              {errors.name && <div className="form-error" data-testid="name-error">{errors.name}</div>}
            </div>

            <div className="form-group">
              <label htmlFor="project-target-url" className="form-label">Target Application URL *</label>
              <input
                id="project-target-url"
                data-testid="project-url-input"
                className="form-input"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="http://localhost:8001 or https://app.example.com"
              />
              {errors.targetUrl && <div className="form-error" data-testid="url-error">{errors.targetUrl}</div>}
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label htmlFor="project-description" className="form-label">Description (Optional)</label>
              <textarea
                id="project-description"
                data-testid="project-description-input"
                className="form-textarea"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief summary of the application under test..."
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" onClick={onClose} className="btn btn-secondary" disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting} data-testid="project-submit-btn">
              {submitting ? 'Saving...' : initialData ? 'Save Changes' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
