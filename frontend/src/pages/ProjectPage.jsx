import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../api/client';
import { Navbar } from '../components/Navbar';
import { ProjectDialog } from '../components/ProjectDialog';
import { CredentialDialog } from '../components/CredentialDialog';

export function ProjectPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [project, setProject] = useState(null);
  const [credentials, setCredentials] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

      // In Phase 4, documents and runs APIs will be hooked in subsequent phases
      setDocuments([]);
      setRuns([]);
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
                <h2>Requirements & Documents</h2>
              </div>
              
              {documents.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', border: '1px dashed var(--border-color)', borderRadius: '6px' }}>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>
                    Upload your requirements so the agent knows what to test.
                  </p>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
                    Supported formats: PDF, Markdown, TXT, JSON (up to 10MB)
                  </p>
                </div>
              ) : (
                <div>
                  {/* Documents list will be rendered in Phase 5 */}
                </div>
              )}
            </div>

            {/* Test Runs Card */}
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h2>Test Runs</h2>
                <button
                  className="btn btn-primary"
                  disabled={documents.length === 0}
                  title={documents.length === 0 ? 'Upload requirements to enable test runs' : 'Start a new test run'}
                  data-testid="start-run-btn"
                >
                  Start Test Run
                </button>
              </div>

              {runs.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                  No runs yet. Start your first test run.
                </div>
              ) : (
                <div>
                  {/* Test runs list */}
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
