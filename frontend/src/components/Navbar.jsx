import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function Navbar({ breadcrumbs = [] }) {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header style={{ borderBottom: '1px solid var(--border-color)', backgroundColor: '#FFFFFF' }}>
      <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)', textDecoration: 'none' }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              backgroundColor: 'var(--accent-color)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: '14px'
            }}>
              TP
            </div>
            <span style={{ fontWeight: 600, fontSize: '16px' }}>TestPilot AI</span>
          </Link>

          {breadcrumbs.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '13px' }}>
              <span>/</span>
              {breadcrumbs.map((bc, idx) => (
                <React.Fragment key={idx}>
                  {bc.href ? (
                    <Link to={bc.href} style={{ color: 'var(--text-secondary)' }}>{bc.label}</Link>
                  ) : (
                    <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{bc.label}</span>
                  )}
                  {idx < breadcrumbs.length - 1 && <span>/</span>}
                </React.Fragment>
              ))}
            </div>
          )}
        </div>

        {isAuthenticated && user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{user.email}</span>
            <button
              onClick={handleLogout}
              className="btn btn-secondary"
              style={{ padding: '6px 12px', fontSize: '13px' }}
              aria-label="Log out"
            >
              Log out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
