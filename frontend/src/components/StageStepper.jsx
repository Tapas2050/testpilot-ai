import React from 'react';

const STAGES = [
  { key: 'PLANNING', label: 'Planning' },
  { key: 'EXECUTING', label: 'Executing' },
  { key: 'ANALYZING', label: 'Analyzing' },
  { key: 'REPORTING', label: 'Reporting' },
];

export function StageStepper({ currentStage, runStatus }) {
  const currentStageIndex = STAGES.findIndex((s) => s.key === currentStage);
  const isCompleted = runStatus === 'COMPLETED';
  const isFailed = runStatus === 'FAILED';
  const isCancelled = runStatus === 'CANCELLED';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px',
        backgroundColor: '#F8FAFC',
        border: '1px solid #E2E8F0',
        borderRadius: '8px',
        marginBottom: '24px',
      }}
    >
      {STAGES.map((stage, idx) => {
        let state = 'pending'; // 'completed' | 'active' | 'pending' | 'failed'

        if (isCompleted) {
          state = 'completed';
        } else if (isFailed && idx === currentStageIndex) {
          state = 'failed';
        } else if (isCancelled && idx === currentStageIndex) {
          state = 'cancelled';
        } else if (idx < currentStageIndex) {
          state = 'completed';
        } else if (idx === currentStageIndex) {
          state = 'active';
        }

        const circleStyles = {
          completed: { bg: '#16A34A', border: '#16A34A', color: '#FFFFFF', icon: '✓' },
          active: { bg: '#2563EB', border: '#2563EB', color: '#FFFFFF', icon: idx + 1 },
          failed: { bg: '#DC2626', border: '#DC2626', color: '#FFFFFF', icon: '✕' },
          cancelled: { bg: '#64748B', border: '#64748B', color: '#FFFFFF', icon: '—' },
          pending: { bg: '#FFFFFF', border: '#CBD5E1', color: '#64748B', icon: idx + 1 },
        }[state];

        return (
          <React.Fragment key={stage.key}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  fontWeight: 600,
                  backgroundColor: circleStyles.bg,
                  border: `2px solid ${circleStyles.border}`,
                  color: circleStyles.color,
                  boxShadow: state === 'active' ? '0 0 0 3px rgba(37, 99, 235, 0.2)' : 'none',
                  transition: 'all 0.2s ease',
                }}
              >
                {circleStyles.icon}
              </div>
              <div>
                <div
                  style={{
                    fontSize: '14px',
                    fontWeight: state === 'active' ? 600 : 500,
                    color: state === 'pending' ? '#64748B' : '#0F172A',
                  }}
                >
                  {stage.label}
                </div>
                <div style={{ fontSize: '11px', color: '#94A3B8', textTransform: 'capitalize' }}>
                  {state}
                </div>
              </div>
            </div>
            {idx < STAGES.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: '2px',
                  backgroundColor:
                    idx < currentStageIndex || isCompleted ? '#16A34A' : '#E2E8F0',
                  margin: '0 12px',
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
