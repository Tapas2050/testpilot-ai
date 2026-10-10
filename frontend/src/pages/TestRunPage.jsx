import React, { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useRunStatus } from '../hooks/useRunStatus';
import { StageStepper } from '../components/StageStepper';
import { Banner } from '../components/Banner';
import { ScreenshotViewer } from '../components/ScreenshotViewer';
import { getStatusStyle } from '../utils/statusStyles';

export function TestRunPage() {
  const { id: runId } = useParams();
  const navigate = useNavigate();

  const {
    run,
    testCases,
    results,
    loading,
    error,
    cancelling,
    cancelRun,
    isTerminal,
  } = useRunStatus(runId);

  const [expandedTestIds, setExpandedTestIds] = useState({});

  const toggleExpand = (testId) => {
    setExpandedTestIds((prev) => ({
      ...prev,
      [testId]: !prev[testId],
    }));
  };

  if (loading && !run) {
    return (
      <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto', textAlign: 'center' }}>
        <p style={{ color: '#64748B' }}>Loading test run details...</p>
      </div>
    );
  }

  if (error && !run) {
    return (
      <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto' }}>
        <Banner type="error" title="Failed to load test run" message={error} />
        <Link to="/" style={{ color: '#4F46E5', textDecoration: 'none', fontWeight: 500 }}>
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  const resultsMap = (results || []).reduce((acc, r) => {
    acc[r.test_case_id] = r;
    return acc;
  }, {});

  const totalTests = testCases.length;
  const completedTests = results.length;
  const passCount = results.filter((r) => r.status === 'PASSED').length;
  const failCount = results.filter((r) => r.status === 'FAILED').length;

  const statusStyle = getStatusStyle(run?.status);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FFFFFF', color: '#0F172A', paddingBottom: '60px' }}>
      <header
        style={{
          borderBottom: '1px solid #E2E8F0',
          padding: '16px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#64748B' }}>
          <Link to="/" style={{ color: '#64748B', textDecoration: 'none' }}>
            Dashboard
          </Link>
          <span>/</span>
          {run?.project_id && (
            <>
              <Link to={`/projects/${run.project_id}`} style={{ color: '#64748B', textDecoration: 'none' }}>
                Project
              </Link>
              <span>/</span>
            </>
          )}
          <span style={{ color: '#0F172A', fontWeight: 500 }}>
            Run #{runId?.slice(0, 8)}
          </span>
        </div>
      </header>

      <main style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px 24px' }}>
        {/* Header with Title and Actions */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '24px',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>
                Test Run #{runId?.slice(0, 8)}
              </h1>
              <span
                style={{
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  fontWeight: 600,
                  backgroundColor: statusStyle.bg,
                  color: statusStyle.text,
                  border: `1px solid ${statusStyle.border}`,
                }}
              >
                {run?.status || 'QUEUED'}
              </span>
            </div>
            <p style={{ margin: '6px 0 0', color: '#64748B', fontSize: '14px' }}>
              Stage: <strong>{run?.agent_stage || 'INITIALIZING'}</strong>
              {totalTests > 0 && ` • Progress: ${completedTests}/${totalTests} tests`}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            {!isTerminal && (
              <button
                type="button"
                onClick={cancelRun}
                disabled={cancelling}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#FFFFFF',
                  color: '#DC2626',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: cancelling ? 'not-allowed' : 'pointer',
                }}
              >
                {cancelling ? 'Cancelling...' : 'Cancel Run'}
              </button>
            )}

            {run?.status === 'COMPLETED' && (
              <button
                type="button"
                onClick={() => navigate(`/runs/${runId}/report`)}
                style={{
                  padding: '8px 18px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: '#4F46E5',
                  color: '#FFFFFF',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                }}
              >
                View Full Report →
              </button>
            )}
          </div>
        </div>

        {/* Banners */}
        {run?.status === 'FAILED' && (
          <Banner
            type="error"
            title="Test Run Failed"
            message={`Execution stopped during stage ${run?.agent_stage || 'UNKNOWN'}: ${run?.error_message || 'An unexpected execution error occurred.'}`}
          />
        )}

        {run?.status === 'CANCELLED' && (
          <Banner
            type="neutral"
            title="Test Run Cancelled"
            message="This test run was cancelled by the user. Partial results captured prior to cancellation are displayed below."
          />
        )}

        {/* Stage Stepper */}
        <StageStepper currentStage={run?.agent_stage} runStatus={run?.status} />

        {/* Live Progress Summary */}
        {totalTests > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '16px',
              marginBottom: '28px',
            }}
          >
            <div style={{ padding: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '12px', color: '#64748B' }}>Total Tests Planned</div>
              <div style={{ fontSize: '20px', fontWeight: 600, marginTop: '4px' }}>{totalTests}</div>
            </div>
            <div style={{ padding: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '12px', color: '#64748B' }}>Completed</div>
              <div style={{ fontSize: '20px', fontWeight: 600, marginTop: '4px' }}>{completedTests}</div>
            </div>
            <div style={{ padding: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '12px', color: '#16A34A' }}>Passed</div>
              <div style={{ fontSize: '20px', fontWeight: 600, marginTop: '4px', color: '#16A34A' }}>{passCount}</div>
            </div>
            <div style={{ padding: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '12px', color: '#DC2626' }}>Failed</div>
              <div style={{ fontSize: '20px', fontWeight: 600, marginTop: '4px', color: '#DC2626' }}>{failCount}</div>
            </div>
          </div>
        )}

        {/* Test Plan & Execution Details */}
        <div style={{ border: '1px solid #E2E8F0', borderRadius: '8px', overflow: 'hidden' }}>
          <div
            style={{
              padding: '16px 20px',
              backgroundColor: '#F8FAFC',
              borderBottom: '1px solid #E2E8F0',
              fontWeight: 600,
              fontSize: '16px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>Test Plan & Execution</span>
            <span style={{ fontSize: '12px', fontWeight: 400, color: '#64748B' }}>
              {testCases.length} scenario{testCases.length === 1 ? '' : 's'}
            </span>
          </div>

          {testCases.length === 0 ? (
            <div style={{ padding: '36px', textAlign: 'center', color: '#64748B' }}>
              {run?.status === 'QUEUED' || run?.agent_stage === 'PLANNING'
                ? 'Planning tests from your requirements...'
                : 'No test scenarios recorded for this run.'}
            </div>
          ) : (
            <div>
              {testCases.map((tc) => {
                const res = resultsMap[tc.id];
                const isExpanded = !!expandedTestIds[tc.id];

                const testStatusStyle = res ? getStatusStyle(res.status) : getStatusStyle('PENDING');
                const resultBadge = (
                  <span
                    style={{
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: testStatusStyle.bg,
                      color: testStatusStyle.text,
                      border: `1px solid ${testStatusStyle.border}`,
                    }}
                  >
                    {res ? res.status : 'Pending'}
                  </span>
                );

                return (
                  <div
                    key={tc.id}
                    style={{
                      borderBottom: '1px solid #E2E8F0',
                      transition: 'background-color 0.1s ease',
                    }}
                  >
                    <div
                      onClick={() => toggleExpand(tc.id)}
                      style={{
                        padding: '14px 20px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        backgroundColor: isExpanded ? '#F8FAFC' : '#FFFFFF',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span
                          style={{
                            fontFamily: 'monospace',
                            fontSize: '12px',
                            fontWeight: 600,
                            color: '#4F46E5',
                          }}
                        >
                          {tc.test_key}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 500 }}>{tc.title}</span>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 6px',
                            backgroundColor: '#F1F5F9',
                            color: '#475569',
                            borderRadius: '4px',
                          }}
                        >
                          {tc.priority}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        {resultBadge}
                        <span style={{ color: '#94A3B8', fontSize: '12px' }}>
                          {isExpanded ? '▲' : '▼'}
                        </span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div
                        style={{
                          padding: '16px 20px',
                          backgroundColor: '#FAFAFA',
                          borderTop: '1px solid #E2E8F0',
                          fontSize: '13px',
                        }}
                      >
                        <div style={{ marginBottom: '12px' }}>
                          <strong>Source Requirement: </strong>
                          <span style={{ color: '#4F46E5' }}>{tc.source_requirement}</span>
                        </div>
                        {tc.description && (
                          <div style={{ marginBottom: '12px', color: '#475569' }}>
                            <strong>Description: </strong> {tc.description}
                          </div>
                        )}
                        {tc.preconditions && (
                          <div style={{ marginBottom: '12px', color: '#475569' }}>
                            <strong>Preconditions: </strong> {tc.preconditions}
                          </div>
                        )}
                        <div style={{ marginBottom: '12px' }}>
                          <strong>Planned Steps:</strong>
                          <ol style={{ margin: '6px 0 0 20px', padding: 0, color: '#334155' }}>
                            {(Array.isArray(tc.steps) ? tc.steps : []).map((step, sIdx) => (
                              <li key={sIdx} style={{ marginBottom: '4px' }}>
                                {typeof step === 'string' ? step : step.action || JSON.stringify(step)}
                              </li>
                            ))}
                          </ol>
                        </div>

                        {res && (
                          <div
                            style={{
                              marginTop: '16px',
                              padding: '12px',
                              backgroundColor: '#FFFFFF',
                              borderRadius: '6px',
                              border: '1px solid #E2E8F0',
                            }}
                          >
                            <div style={{ fontWeight: 600, marginBottom: '8px' }}>
                              Execution Results
                            </div>
                            {res.observations && (
                              <div style={{ marginBottom: '8px', color: '#475569' }}>
                                <strong>Observations: </strong> {res.observations}
                              </div>
                            )}

                            {res.action_log && res.action_log.length > 0 && (
                              <div style={{ marginTop: '10px' }}>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
                                  Action Log:
                                </div>
                                <div
                                  style={{
                                    backgroundColor: '#0F172A',
                                    color: '#F8FAFC',
                                    fontFamily: 'monospace',
                                    fontSize: '12px',
                                    padding: '10px',
                                    borderRadius: '4px',
                                    maxHeight: '160px',
                                    overflowY: 'auto',
                                  }}
                                >
                                  {res.action_log.map((action, aIdx) => (
                                    <div key={aIdx} style={{ marginBottom: '2px' }}>
                                      &gt; Step {action.step}: {action.tool} (
                                      {JSON.stringify(action.arguments || {})})
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {res.evidence_paths && res.evidence_paths.length > 0 && (
                              <div style={{ marginTop: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '6px' }}>
                                  Captured Screenshots:
                                </div>
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                  {res.evidence_paths.map((p, pIdx) => {
                                    const filename = p.split(/[\\/]/).pop();
                                    return (
                                      <ScreenshotViewer
                                        key={pIdx}
                                        runId={runId}
                                        filename={filename}
                                        caption={`Evidence ${tc.test_key}`}
                                      />
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
