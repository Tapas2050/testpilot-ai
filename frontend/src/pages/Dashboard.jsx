import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Navbar } from '../components/Navbar';
import { ProjectDialog } from '../components/ProjectDialog';

export function Dashboard() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await api.projects.list();
      setProjects(data);
    } catch (err) {
      setError(err.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async (data) => {
    const newProj = await api.projects.create(data);
    setProjects([newProj, ...projects]);
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FFFFFF' }}>
      <Navbar />

      <main className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1>Projects</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '2px' }}>
              Applications configured for autonomous AI test runs
            </p>
          </div>
          <button
            onClick={() => setIsDialogOpen(true)}
            className="btn btn-primary"
            data-testid="new-project-btn"
          >
            + New Project
          </button>
        </div>

        {error && (
          <div className="badge badge-fail" style={{ width: '100%', padding: '12px', marginBottom: '16px', borderRadius: '6px' }}>
            {error}
          </div>
        )}

        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Loading projects...
          </div>
        ) : projects.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: 'var(--accent-light)',
              color: 'var(--accent-color)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
              marginBottom: '16px'
            }}>
              📁
            </div>
            <h2>No projects yet. Create one to start testing.</h2>
            <p style={{ color: 'var(--text-secondary)', maxWidth: '400px', margin: '8px auto 20px' }}>
              Add your application's target URL and test credentials to let the AI agent plan and run tests.
            </p>
            <button
              onClick={() => setIsDialogOpen(true)}
              className="btn btn-primary"
            >
              Create Your First Project
            </button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {projects.map((proj) => (
              <Link
                key={proj.id}
                to={`/projects/${proj.id}`}
                style={{ textDecoration: 'none', color: 'inherit' }}
                data-testid={`project-card-${proj.id}`}
              >
                <div
                  className="card"
                  style={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    transition: 'transform 0.15s, border-color 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-color)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
                >
                  <div>
                    <h3 style={{ marginBottom: '8px' }}>{proj.name}</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '12px', minHeight: '38px' }}>
                      {proj.description || 'No description provided.'}
                    </p>
                  </div>
                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="font-mono" style={{ fontSize: '12px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '200px' }}>
                      {proj.target_url}
                    </span>
                    <span className="badge badge-info" style={{ fontSize: '11px' }}>Ready</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>

      <ProjectDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onSubmit={handleCreateProject}
      />
    </div>
  );
}
