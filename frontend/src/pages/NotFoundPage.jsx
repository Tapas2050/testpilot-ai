import React from 'react';
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#FFFFFF',
        padding: '24px',
        textAlign: 'center',
        color: '#0F172A',
      }}
    >
      <div style={{ maxWidth: '460px', width: '100%' }}>
        <div
          style={{
            fontSize: '72px',
            fontWeight: 700,
            color: '#4F46E5',
            lineHeight: 1,
            marginBottom: '16px',
          }}
        >
          404
        </div>
        <h1 style={{ fontSize: '24px', fontWeight: 600, marginBottom: '8px' }}>
          Page Not Found
        </h1>
        <p style={{ color: '#64748B', fontSize: '14px', marginBottom: '28px', lineHeight: 1.5 }}>
          The requested page does not exist or has been moved. Check the URL or return to your dashboard.
        </p>
        <Link
          to="/"
          style={{
            display: 'inline-block',
            padding: '10px 20px',
            backgroundColor: '#4F46E5',
            color: '#FFFFFF',
            borderRadius: '6px',
            textDecoration: 'none',
            fontSize: '14px',
            fontWeight: 500,
          }}
        >
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
