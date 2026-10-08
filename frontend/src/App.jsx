import { useState, useEffect } from 'react'

function App() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const checkHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://localhost:8000/health')
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const data = await res.json()
      setHealth(data)
    } catch (err) {
      setError(err.message || 'Failed to connect to backend')
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkHealth()
  }, [])

  return (
    <div className="app-container">
      <header className="header">
        <div className="logo-group">
          <div className="logo-badge">TP</div>
          <h1 className="app-title">TestPilot AI</h1>
        </div>
        <span className="phase-pill">Phase 1: Foundation</span>
      </header>

      <main>
        <section className="card">
          <h2 className="card-title">Backend Connectivity</h2>
          <p className="card-desc">
            Live health verification against FastAPI API, PostgreSQL 18 with pgvector, and Redis.
          </p>

          <div style={{ marginBottom: '1rem' }}>
            <button className="button" onClick={checkHealth} disabled={loading}>
              {loading ? 'Checking status...' : 'Refresh Health Check'}
            </button>
          </div>

          {error && (
            <div style={{ color: 'var(--fail-color)', fontSize: '0.9rem', marginBottom: '1rem' }}>
              Backend unreachable ({error}). Ensure FastAPI is running on port 8000.
            </div>
          )}

          <div className="status-grid">
            <div className="status-item">
              <div className="status-label">API Status</div>
              <div className="status-value">
                <span className={`indicator ${health?.status === 'ok' ? 'healthy' : 'unhealthy'}`} />
                {health?.api?.toUpperCase() || (loading ? 'CHECKING...' : 'OFFLINE')}
              </div>
            </div>

            <div className="status-item">
              <div className="status-label">PostgreSQL 18</div>
              <div className="status-value">
                <span className={`indicator ${health?.database?.status === 'healthy' ? 'healthy' : 'unhealthy'}`} />
                {health?.database?.status?.toUpperCase() || (loading ? 'CHECKING...' : 'OFFLINE')}
              </div>
            </div>

            <div className="status-item">
              <div className="status-label">pgvector Extension</div>
              <div className="status-value">
                <span className={`indicator ${health?.database?.pgvector_enabled ? 'healthy' : 'unhealthy'}`} />
                {health?.database?.pgvector_enabled ? 'ENABLED' : (loading ? 'CHECKING...' : 'DISABLED')}
              </div>
            </div>

            <div className="status-item">
              <div className="status-label">Redis Cache</div>
              <div className="status-value">
                <span className={`indicator ${health?.redis?.status === 'healthy' ? 'healthy' : 'unhealthy'}`} />
                {health?.redis?.status?.toUpperCase() || (loading ? 'CHECKING...' : 'OFFLINE')}
              </div>
            </div>
          </div>
        </section>

        <section className="card">
          <h2 className="card-title">Foundation Overview</h2>
          <p className="card-desc">
            TestPilot AI automated testing platform foundation setup.
          </p>
          <ul className="roadmap-list">
            <li className="roadmap-item">
              <span className="badge-done">Phase 1</span>
              <span>Foundation: FastAPI, PostgreSQL 18 + pgvector, Redis, uv, React placeholder</span>
            </li>
            <li className="roadmap-item">
              <span className="badge-pending">Phase 2</span>
              <span>Authentication Backend: User & Session models, JWT, me & logout</span>
            </li>
            <li className="roadmap-item">
              <span className="badge-pending">Phase 3</span>
              <span>Project Management Backend: CRUD, target URL validation, credential encryption</span>
            </li>
            <li className="roadmap-item">
              <span className="badge-pending">Phase 4</span>
              <span>Frontend Auth and Project Shell: Dashboard, Project screens</span>
            </li>
          </ul>
        </section>
      </main>
    </div>
  )
}

export default App
