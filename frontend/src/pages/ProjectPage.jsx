import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import { Navbar } from '../components/Navbar';
import { ProjectDialog } from '../components/ProjectDialog';
import { CredentialDialog } from '../components/CredentialDialog';

export function ProjectPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [project, setProject] = useState(null);
  const [credentials, setCredentials] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isCredOpen, setIsCredOpen] = useState(false);

  const fetchProjectData = async () => {
    try {
      setLoading(true);
      setError('');
      const proj = await api.projects.get(id);
      setProject(proj);

      const creds = await api.projects.listCredentials(id);
      setCredentials(creds);

      const docs = await api.documents.list(id);
      setDocuments(docs);

      try {
        const runList = await api.runs.list(id);
        setRuns(runList);
      } catch {
        // Run list endpoint fallback
        setRuns([]);
      }
    } catch (err) {
      setError(err.message || 'Failed to load project');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjectData();
  }, [id]);

  const handleUpdateProject = async (data) => {
    const updated = await api.projects.update(id, data);
    setProject(updated);
  };

  const handleDeleteProject = async () => {
    if (window.confirm(`Are you sure you want to delete project "${project.name}"? This action cannot be undone.`)) {
      try {
        await api.projects.delete(id);
        navigate('/');
      } catch (err) {
        alert(err.message || 'Failed to delete project');
      }
    }
  };

  const handleAddCredential = async (data) => {
    const newCred = await api.projects.addCredential(id, data);
    setCredentials([...credentials, newCred]);
  };

  const handleDeleteCredential = async (credId) => {
    if (window.confirm('Delete this credential?')) {
      try {
        await api.projects.deleteCredential(id, credId);
        setCredentials(credentials.filter((c) => c.id !== credId));
      } catch (err) {
        alert(err.message || 'Failed to delete credential');
      }
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    setUploadError('');
    setUploading(true);
    try {
      const newDoc = await api.documents.upload(id, file);
      setDocuments((prev) => [newDoc, ...prev]);
    } catch (err) {
      setUploadError(err.message || 'Failed to upload document');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (window.confirm('Delete this document?')) {
      try {
        await api.documents.delete(docId);
        setDocuments(documents.filter((d) => d.id !== docId));
      } catch (err) {
        alert(err.message || 'Failed to delete document');
      }
    }
  };

  const [startingRun, setStartingRun] = useState(false);

  const handleStartRun = async () => {
    if (documents.length === 0) return;
    try {
      setStartingRun(true);
      const newRun = await api.runs.create(id);
      navigate(`/projects/${id}/runs/${newRun.id}`);
    } catch (err) {
      alert(err.message || 'Failed to start test run');
    } finally {
      setStartingRun(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#FFFFFF' }}>
        <Navbar />
        <main className="container" style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Loading project details...
        </main>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#FFFFFF' }}>
        <Navbar />
        <main className="container" style={{ padding: '40px 0', textAlign: 'center' }}>
          <h2>Not Found</h2>
          <p style={{ color: 'var(--text-secondary)', margin: '12px 0 20px' }}>
            {error || 'The requested project does not exist.'}
          </p>
          <Link to="/" className="btn btn-primary">
            Back to Dashboard
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FFFFFF' }}>
      <Navbar />

      <main className="container">
        {/* Breadcrumbs */}
        <nav style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }} aria-label="Breadcrumb">
          <Link to="/" style={{ color: 'var(--accent-color)', textDecoration: 'none' }}>Dashboard</Link>
          <span style={{ margin: '0 8px' }}>/</span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{project.name}</span>
        </nav>

        {/* Project Header */}
        <div className="card" style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h1 style={{ marginBottom: '6px' }}>{project.name}</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '12px' }}>
                {project.description || 'No description provided.'}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Target URL:</span>
                <a
                  href={project.target_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono"
                  style={{ color: 'var(--accent-color)', textDecoration: 'none' }}
                >
                  {project.target_url}
                </a>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => setIsEditOpen(true)}
                className="btn btn-secondary"
                data-testid="edit-project-btn"
              >
                Edit Project
              </button>
              <button
                onClick={handleDeleteProject}
                className="btn btn-danger"
                data-testid="delete-project-btn"
              >
                Delete
              </button>
            </div>
          </div>
        </div>

        {/* Main Grid: Left Column (Docs & History), Right Column (Credentials) */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
          
          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* Requirements & Documents Card */}
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2>Requirements & Documents</h2>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '2px' }}>
                    Uploaded requirements are sent to external LLMs for test planning.
                  </p>
                </div>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="btn btn-secondary"
                  disabled={uploading}
                  data-testid="upload-doc-btn"
                >
                  + Upload Document
                </button>
                <input
                  type="file"
                  ref={fileInputRef}
                  style={{ display: 'none' }}
                  accept=".pdf,.txt,.md,.markdown,.json"
                  onChange={(e) => handleFileUpload(e.target.files?.[0])}
                  data-testid="file-input"
                />
              </div>

              {uploadError && (
                <div className="badge badge-fail" style={{ width: '100%', padding: '10px', marginBottom: '12px', borderRadius: '4px' }}>
                  {uploadError}
                </div>
              )}

              {uploading && (
                <div style={{ padding: '16px', marginBottom: '12px', backgroundColor: 'var(--surface-color)', borderRadius: '6px', textAlign: 'center', color: 'var(--accent-color)', fontSize: '13px' }}>
                  Processing document and extracting text...
                </div>
              )}

              {/* Dropzone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleFileUpload(file);
                }}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  textAlign: 'center',
                  padding: '24px 16px',
                  border: isDragging ? '2px dashed var(--accent-color)' : '1px dashed var(--border-color)',
                  backgroundColor: isDragging ? 'rgba(79, 70, 229, 0.05)' : '#FFFFFF',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  marginBottom: documents.length > 0 ? '16px' : 0,
                  transition: 'border-color 0.15s, background-color 0.15s',
                }}
                data-testid="document-dropzone"
              >
                <p style={{ color: 'var(--text-primary)', fontSize: '13px', fontWeight: 500, marginBottom: '4px' }}>
                  Click to browse or drop file here
                </p>
                <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                  Supported formats: PDF, Markdown, TXT, JSON (up to 10MB)
                </p>
              </div>

              {/* Documents List */}
              {documents.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--text-secondary)', fontSize: '13px' }}>
                  Upload your requirements so the agent knows what to test.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '12px',
                        backgroundColor: '#FFFFFF',
                        border: '1px solid var(--border-color)',
                        borderRadius: '6px',
                      }}
                      data-testid={`document-item-${doc.id}`}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span className="badge badge-info" style={{ textTransform: 'uppercase', fontSize: '10px' }}>
                            {doc.file_type}
                          </span>
                          <span style={{ fontWeight: 500, fontSize: '13px' }}>{doc.original_name}</span>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', gap: '12px' }}>
                          <span>Size: {formatFileSize(doc.size_bytes)}</span>
                          <span>
                            Status:{' '}
                            <span style={{
                              color: doc.extraction_status === 'SUCCESS' ? 'var(--pass-color)' : 'var(--fail-color)',
                              fontWeight: 600
                            }}>
                              {doc.extraction_status}
                            </span>
                          </span>
                        </div>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteDocument(doc.id);
                        }}
                        className="btn btn-danger"
                        style={{ padding: '4px 8px', fontSize: '12px' }}
                        data-testid={`delete-doc-btn-${doc.id}`}
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Test Runs Card */}
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h2>Test Runs</h2>
                <button
                  onClick={handleStartRun}
                  disabled={documents.length === 0 || startingRun}
                  className="btn btn-primary"
                  title={documents.length === 0 ? 'Upload requirements to enable test runs' : 'Start a new test run'}
                  data-testid="start-run-btn"
                >
                  {startingRun ? 'Starting Run...' : 'Start Test Run'}
                </button>
              </div>

              {runs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                  No runs yet. Start your first test run.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {runs.map((r) => {
                    const statusClass = {
                      COMPLETED: 'badge-pass',
                      FAILED: 'badge-fail',
                      RUNNING: 'badge-info',
                      CANCELLED: 'badge-secondary',
                      QUEUED: 'badge-warning',
                    }[r.status] || 'badge-secondary';

                    return (
                      <div
                        key={r.id}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '12px 16px',
                          backgroundColor: '#FFFFFF',
                          border: '1px solid var(--border-color)',
                          borderRadius: '6px',
                        }}
                        data-testid={`run-row-${r.id}`}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                            <Link
                              to={`/projects/${id}/runs/${r.id}`}
                              style={{ fontWeight: 600, color: 'var(--accent-color)', textDecoration: 'none' }}
                            >
                              Run #{r.id.slice(0, 8)}
                            </Link>
                            <span className={`badge ${statusClass}`}>{r.status}</span>
                            {r.report && (
                              <span style={{ fontSize: '12px', fontWeight: 600, color: '#16A34A' }}>
                                {r.report.pass_percentage ?? r.report.pass_rate}% pass
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                            Stage: {r.agent_stage} •{' '}
                            {r.started_at ? new Date(r.started_at).toLocaleString() : 'Not started'}
                          </div>
                        </div>

                        <div style={{ display: 'flex', gap: '8px' }}>
                          <Link
                            to={`/projects/${id}/runs/${r.id}`}
                            className="btn btn-secondary"
                            style={{ padding: '6px 10px', fontSize: '12px', textDecoration: 'none' }}
                          >
                            View Run
                          </Link>
                          {r.status === 'COMPLETED' && (
                            <Link
                              to={`/runs/${r.id}/report`}
                              className="btn btn-primary"
                              style={{ padding: '6px 10px', fontSize: '12px', textDecoration: 'none' }}
                            >
                              Report
                            </Link>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Test Credentials */}
          <div>
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2>Test Credentials</h2>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px', marginTop: '2px' }}>
                    Roles and accounts for the agent to use during test execution.
                  </p>
                </div>
                <button
                  onClick={() => setIsCredOpen(true)}
                  className="btn btn-secondary"
                  data-testid="add-cred-btn"
                >
                  + Add Credential
                </button>
              </div>

              {credentials.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                  No test credentials added yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {credentials.map((cred) => (
                    <div
                      key={cred.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '12px',
                        backgroundColor: '#FFFFFF',
                        border: '1px solid var(--border-color)',
                        borderRadius: '6px',
                      }}
                      data-testid={`credential-item-${cred.id}`}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span className="badge badge-info">{cred.role_label || cred.role}</span>
                          <span style={{ fontWeight: 500, fontSize: '13px' }}>{cred.username}</span>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          Password encrypted with Fernet
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteCredential(cred.id)}
                        className="btn btn-danger"
                        style={{ padding: '4px 8px', fontSize: '12px' }}
                        data-testid={`delete-cred-btn-${cred.id}`}
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

        </div>
      </main>

      <ProjectDialog
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        onSubmit={handleUpdateProject}
        initialData={project}
      />

      <CredentialDialog
        isOpen={isCredOpen}
        onClose={() => setIsCredOpen(false)}
        onSubmit={handleAddCredential}
      />
    </div>
  );
}
