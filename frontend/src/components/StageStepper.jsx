import React from 'react';

const STAGES = [
  { key: 'QUEUED', label: 'Queued' },
  { key: 'PLANNING', label: 'Planning' },
  { key: 'EXECUTING', label: 'Executing' },
  { key: 'ANALYZING', label: 'Analyzing' },
  { key: 'REPORTING', label: 'Reporting' },
  { key: 'COMPLETED', label: 'Completed' },
];

export function StageStepper({ currentStage, runStatus }) {
  const isCompleted = runStatus === 'COMPLETED';
  const isFailed = runStatus === 'FAILED';
  const isCancelled = runStatus === 'CANCELLED';

  // Normalize current stage index
  const normalizedStage = (currentStage || (isCompleted ? 'COMPLETED' : 'QUEUED')).toUpperCase();
  let currentStageIndex = STAGES.findIndex((s) => s.key === normalizedStage);
  if (currentStageIndex === -1) {
    currentStageIndex = isCompleted ? 5 : 0;
  }

  return (
    <div
      style={{
        padding: '20px 24px',
        backgroundColor: '#F8FAFC',
        border: '1px solid #E2E8F0',
        borderRadius: '8px',
        marginBottom: '24px',
      }}
    >
      <style>{`
        @keyframes stagePulse {
          0% {
            box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
            transform: scale(1);
          }
          50% {
            box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.15);
            transform: scale(1.05);
          }
          100% {
            box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4);
            transform: scale(1);
          }
        }
        .stage-active-pulse {
          animation: stagePulse 2s infinite ease-in-out;
        }
      `}</style>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {STAGES.map((stage, idx) => {
          let state = 'pending'; // 'completed' | 'active' | 'pending' | 'failed' | 'cancelled'

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
            active: { bg: '#2563EB', border: '#2563EB', color: '#FFFFFF', icon: String(idx + 1) },
            failed: { bg: '#DC2626', border: '#DC2626', color: '#FFFFFF', icon: '✕' },
            cancelled: { bg: '#64748B', border: '#64748B', color: '#FFFFFF', icon: '—' },
            pending: { bg: '#FFFFFF', border: '#CBD5E1', color: '#64748B', icon: String(idx + 1) },
          }[state] || { bg: '#FFFFFF', border: '#CBD5E1', color: '#64748B', icon: String(idx + 1) };

          const isLineActive =
            idx < currentStageIndex ||
            (isCompleted && idx < STAGES.length - 1);

          return (
            <React.Fragment key={stage.key}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  className={state === 'active' ? 'stage-active-pulse' : ''}
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
                      color: state === 'pending' ? '#64748B' : state === 'failed' ? '#DC2626' : '#0F172A',
                    }}
                  >
                    {stage.label}
                  </div>
                  <div
                    style={{
                      fontSize: '11px',
                      color: state === 'failed' ? '#DC2626' : '#94A3B8',
                      textTransform: 'capitalize',
                    }}
                  >
                    {state}
                  </div>
                </div>
              </div>
              {idx < STAGES.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: '2px',
                    backgroundColor: isLineActive ? '#16A34A' : '#E2E8F0',
                    margin: '0 8px',
                  }}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
