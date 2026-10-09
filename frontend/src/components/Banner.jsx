import React from 'react';

export function Banner({ type = 'info', title, message, children }) {
  const styles = {
    error: {
      bg: '#FEF2F2',
      border: '#F87171',
      text: '#991B1B',
      titleColor: '#7F1D1D',
      icon: (
        <svg style={{ width: 20, height: 20, flexShrink: 0 }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    warning: {
      bg: '#FFFBEB',
      border: '#FCD34D',
      text: '#92400E',
      titleColor: '#78350F',
      icon: (
        <svg style={{ width: 20, height: 20, flexShrink: 0 }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
    neutral: {
      bg: '#F1F5F9',
      border: '#CBD5E1',
      text: '#475569',
      titleColor: '#1E293B',
      icon: (
        <svg style={{ width: 20, height: 20, flexShrink: 0 }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    info: {
      bg: '#EFF6FF',
      border: '#93C5FD',
      text: '#1E40AF',
      titleColor: '#1E3A8A',
      icon: (
        <svg style={{ width: 20, height: 20, flexShrink: 0 }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  };

  const style = styles[type] || styles.info;

  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '16px',
        borderRadius: '8px',
        backgroundColor: style.bg,
        border: `1px solid ${style.border}`,
        color: style.text,
        marginBottom: '20px',
      }}
    >
      <div style={{ color: style.titleColor }}>{style.icon}</div>
      <div style={{ flex: 1 }}>
        {title && (
          <div style={{ fontWeight: 600, color: style.titleColor, marginBottom: message || children ? '4px' : 0 }}>
            {title}
          </div>
        )}
        {message && <div style={{ fontSize: '14px', lineHeight: 1.5 }}>{message}</div>}
        {children}
      </div>
    </div>
  );
}
