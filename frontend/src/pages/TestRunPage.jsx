import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useRunStatus } from '../hooks/useRunStatus';
import { StageStepper } from '../components/StageStepper';
import { Banner } from '../components/Banner';
import { ScreenshotViewer } from '../components/ScreenshotViewer';
import { getStatusStyle } from '../utils/statusStyles';
import { api } from '../api/client';

function getFailureHint(stage, errorMsg) {
  const msg = (errorMsg || '').toLowerCase();
  const st = (stage || '').toUpperCase();

  if (msg.includes('did not respond') || msg.includes('is it running')) {
    return 'Make sure the target application is running and accessible at the configured URL.';
  }
  if (msg.includes('playwright mcp') || msg.includes('node process')) {
    return 'Verify Node.js and Playwright MCP server dependencies are installed and accessible.';
  }
  if (
    msg.includes('stored credential') ||
    msg.includes('credential_encryption_key') ||
    msg.includes('authentication failed')
  ) {
    return 'Check that project credentials and encryption keys are correctly configured in Project Settings.';
  }
  if (msg.includes('time limit') || msg.includes('deadline')) {
    return 'The run exceeded its maximum time limit. Consider reducing the scope of test scenarios or checking target responsiveness.';
  }
  if (msg.includes('environment_failure') || msg.includes('tool call timeout')) {
    return 'A browser interaction timed out or the browser environment failed. Check target app performance.';
  }
  if (st === 'PREFLIGHT') {
    return 'Preflight checks failed before starting tests. Review target URL and environment connectivity.';
  }
  if (st === 'PLANNING') {
    return 'Test planning could not be completed. Check project requirements and documentation.';
  }
  return 'Review the error details and system logs before starting a new run.';
}

const ACTION_BADGES = {
  click: { bg: '#E0F2FE', text: '#0369A1' },
  fill: { bg: '#FEF3C7', text: '#B45309' },
  navigate: { bg: '#F3E8FF', text: '#6B21A8' },
  press_key: { bg: '#EDE9FE', text: '#5B21B6' },
  select: { bg: '#CCFBF1', text: '#0F766E' },
  finish: { bg: '#DCFCE7', text: '#15803D' },
  login: { bg: '#FEE2E2', text: '#B91C1C' },
};

function getActionBadgeStyle(action) {
  const key = (action || '').toLowerCase();
  return ACTION_BADGES[key] || { bg: '#F1F5F9', text: '#475569' };
}

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
    isTerminal: hookIsTerminal,
    lastUpdateSeconds,
    isStalled,
  } = useRunStatus(runId);

  const isTerminal = hookIsTerminal || (run?.status ? ['COMPLETED', 'FAILED', 'CANCELLED'].includes(run.status) : false);

  const [expandedTestIds, setExpandedTestIds] = useState({});
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [startingNewRun, setStartingNewRun] = useState(false);
  const feedEndRef = useRef(null);

  // Elapsed-time counter
  useEffect(() => {
    if (!run?.started_at) {
      setElapsedSeconds(0);
      return;
    }
    const startTime = new Date(run.started_at).getTime();

    // Calculate client vs server time offset to align timer with server
    const serverTimeMs = run.server_time ? new Date(run.server_time).getTime() : Date.now();
    const clientOffset = Date.now() - serverTimeMs;

    const updateElapsed = () => {
      const nowServerMs = Date.now() - clientOffset;
      const endTime = run.completed_at ? new Date(run.completed_at).getTime() : nowServerMs;
      const secs = Math.max(0, Math.floor((endTime - startTime) / 1000));
      setElapsedSeconds(secs);
    };

    updateElapsed();
    if (isTerminal) return;

    const interval = setInterval(updateElapsed, 1000);
    return () => clearInterval(interval);
  }, [run?.started_at, run?.completed_at, run?.server_time, isTerminal]);

  // Auto-scroll feed on new events
  const recentEvents = useMemo(() => run?.recent_events || [], [run?.recent_events]);
  useEffect(() => {
    if (feedEndRef.current) {
      feedEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [recentEvents.length]);

  const toggleExpand = (testId) => {
    setExpandedTestIds((prev) => ({
      ...prev,
      [testId]: !prev[testId],
    }));
  };

  const formatDuration = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
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
  const handleStartNewRun = async () => {
    if (!run?.project_id) return;
    try {
      setStartingNewRun(true);
      const newRun = await api.runs.create(run.project_id);
      navigate(`/projects/${run.project_id}/runs/${newRun.id}`);
    } catch (err) {
      alert(err.message || 'Failed to start new test run');
    } finally {
      setStartingNewRun(false);
    }
  };

  const resultsMap = (results || []).reduce((acc, r) => {
    acc[r.test_case_id] = r;
    return acc;
  }, {});

  const totalTests = run?.total_tests || testCases.length || 0;
  const passCount = run?.passed_tests ?? results.filter((r) => r.status === 'PASSED').length;
  const failCount = run?.failed_tests ?? results.filter((r) => r.status === 'FAILED').length;
  const blockedCount =
    run?.blocked_tests ??
    results.filter(
      (r) => r.status === 'BLOCKED' && !(r.error_message || '').startsWith('Not executed:')
    ).length;
  const notRunCount =
    run?.not_run_tests ??
    testCases.filter((tc) => {
      const res = resultsMap[tc.id];
      const st = res ? res.status : tc.status;
      const err = res?.error_message || '';
      return st === 'NOT_RUN' || err.startsWith('Not executed:') || (isTerminal && !res && st === 'PENDING');
    }).length;
  const completedTests = run?.completed_tests ?? (passCount + failCount + blockedCount);
  const progressPercent = totalTests > 0 ? Math.min(100, Math.round((completedTests / totalTests) * 100)) : 0;

  const currentStage = (
    run?.failed_stage ||
    run?.stage ||
    run?.current_stage ||
    run?.agent_stage ||
    (run?.status === 'COMPLETED' ? 'COMPLETED' : 'QUEUED')
  ).toUpperCase();
  const statusStyle = getStatusStyle(run?.status);

  // Friendly state message when in early stages
  let friendlyStateMessage = null;
  if (!isTerminal) {
    if (currentStage === 'QUEUED') {
      friendlyStateMessage = 'Queued: Waiting for worker to start test run...';
    } else if (currentStage === 'PLANNING') {
      friendlyStateMessage = 'Planning tests from your requirements...';
    } else if (currentStage === 'EXECUTING') {
      if (recentEvents.length === 0) {
        friendlyStateMessage = 'Starting the browser and setting up test session...';
      }
    } else if (currentStage === 'ANALYZING') {
      friendlyStateMessage = 'Analyzing test execution results and diagnosing failures...';
    } else if (currentStage === 'REPORTING') {
      friendlyStateMessage = 'Compiling test metrics and generating final report...';
    }
  }

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
              Stage: <strong>{currentStage}</strong>
              {totalTests > 0 && ` • Progress: ${completedTests}/${totalTests} tests`}
              {run?.started_at && ` • Elapsed: ${formatDuration(elapsedSeconds)}`}
              {typeof lastUpdateSeconds === 'number' && (
                <span style={{ fontSize: '12px', color: '#94A3B8', marginLeft: '8px' }}>
                  (Last update {lastUpdateSeconds}s ago)
                </span>
              )}
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
                  transition: 'all 0.15s ease',
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
                  padding: '10px 20px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: '#4F46E5',
                  color: '#FFFFFF',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 2px 4px 0 rgba(79, 70, 229, 0.2)',
                  transition: 'background-color 0.15s ease',
                }}
              >
                View Report →
              </button>
            )}
          </div>
        </div>

        {/* Banners */}
        {!isTerminal && isStalled && (
          <div style={{ marginBottom: '24px' }}>
            <Banner
              type="info"
              title="Waiting for progress"
              message="Waiting for the worker to report progress"
            />
          </div>
        )}
        {run?.status === 'FAILED' && (
          <div style={{ marginBottom: '24px' }}>
            <Banner
              type="error"
              title="Test Run Failed"
              message={`Execution stopped during stage ${currentStage}: ${run?.error_message || 'An unexpected execution error occurred.'}`}
            >
              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#7F1D1D' }}>{`Failed in Stage: ${currentStage}`}</div>
                <div style={{ fontSize: '13px', color: '#7F1D1D' }}>
                  <strong>Hint: </strong>{getFailureHint(currentStage, run?.error_message)}
                </div>
                <div>
                  <button
                    type="button"
                    onClick={handleStartNewRun}
                    disabled={startingNewRun}
                    style={{
                      marginTop: '6px',
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: '#DC2626',
                      color: '#FFFFFF',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: startingNewRun ? 'not-allowed' : 'pointer',
                      boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                    }}
                  >
                    {startingNewRun ? 'Starting...' : 'Start a new run'}
                  </button>
                </div>
              </div>
            </Banner>
          </div>
        )}

        {run?.status === 'CANCELLED' && (
          <div style={{ marginBottom: '24px' }}>
            <Banner
              type="neutral"
              title="Test Run Cancelled"
              message="This test run was cancelled by the user. Partial results captured prior to cancellation are displayed below."
            />
          </div>
        )}

        {/* Stage Stepper */}
        <StageStepper currentStage={currentStage} runStatus={run?.status} failedStage={run?.failed_stage} />

        {/* Overall Progress Bar & Elapsed Time */}
        {totalTests > 0 && (
          <div
            style={{
              marginBottom: '24px',
              padding: '18px 20px',
              backgroundColor: '#F8FAFC',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '10px',
                fontSize: '14px',
              }}
            >
              <div style={{ fontWeight: 600, color: '#0F172A' }}>
                Overall Progress: {completedTests} of {totalTests} tests ({progressPercent}%)
              </div>
              <div style={{ color: '#64748B', fontFamily: 'monospace', fontWeight: 600 }}>
                Elapsed: {formatDuration(elapsedSeconds)}
              </div>
            </div>
            <div
              style={{
                width: '100%',
                height: '8px',
                backgroundColor: '#E2E8F0',
                borderRadius: '4px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${progressPercent}%`,
                  height: '100%',
                  backgroundColor: '#4F46E5',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>
        )}

        {/* Friendly State Callout (when active and waiting for stage progress) */}
        {friendlyStateMessage && (
          <div
            style={{
              padding: '16px 20px',
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              borderRadius: '8px',
              marginBottom: '24px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              color: '#1E40AF',
              fontSize: '14px',
              fontWeight: 500,
            }}
          >
            <div
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: '#2563EB',
                animation: 'pulse 1.5s infinite',
              }}
            />
            <span>{friendlyStateMessage}</span>
          </div>
        )}

        {/* Live Activity Feed for Currently Running Test */}
        {!isTerminal && (
          <div
            style={{
              marginBottom: '28px',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
              overflow: 'hidden',
              backgroundColor: '#FFFFFF',
            }}
          >
            <div
              style={{
                padding: '14px 20px',
                backgroundColor: '#0F172A',
                color: '#FFFFFF',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: '#22C55E',
                    display: 'inline-block',
                  }}
                />
                <span style={{ fontWeight: 600, fontSize: '14px' }}>Live Activity Feed</span>
                {run?.current_test && (
                  <span style={{ fontSize: '13px', color: '#94A3B8' }}>
                    — {run.current_test} (Step {run.current_step || 1})
                  </span>
                )}
              </div>
              <span style={{ fontSize: '12px', color: '#64748B' }}>
                {recentEvents.length} event{recentEvents.length === 1 ? '' : 's'}
              </span>
            </div>

            <div
              style={{
                padding: '16px 20px',
                maxHeight: '260px',
                overflowY: 'auto',
                backgroundColor: '#F8FAFC',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              {recentEvents.length === 0 ? (
                <div style={{ color: '#64748B', fontSize: '13px', fontStyle: 'italic', textAlign: 'center', padding: '16px 0' }}>
                  {friendlyStateMessage || 'Waiting for browser action events...'}
                </div>
              ) : (
                recentEvents.map((ev, idx) => {
                  const badgeStyle = getActionBadgeStyle(ev.action);
                  return (
                    <div
                      key={idx}
                      style={{
                        padding: '10px 14px',
                        backgroundColor: '#FFFFFF',
                        border: '1px solid #E2E8F0',
                        borderRadius: '6px',
                        fontSize: '13px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '12px',
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 600,
                          color: '#64748B',
                          fontFamily: 'monospace',
                          minWidth: '55px',
                        }}
                      >
                        Step {ev.step || idx + 1}
                      </span>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: badgeStyle.bg,
                          color: badgeStyle.text,
                          textTransform: 'uppercase',
                        }}
                      >
                        {ev.action || 'ACTION'}
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {ev.selector && (
                          <span style={{ fontFamily: 'monospace', color: '#0F172A', fontWeight: 500 }}>
                            {ev.selector}{' '}
                          </span>
                        )}
                        {ev.url && (
                          <span style={{ color: '#2563EB', textDecoration: 'underline' }}>
                            {ev.url}{' '}
                          </span>
                        )}
                        {ev.observation && (
                          <span style={{ color: '#475569' }}>
                            — {ev.observation}
                          </span>
                        )}
                        {ev.thought && !ev.observation && (
                          <span style={{ color: '#64748B', fontStyle: 'italic' }}>
                            ({ev.thought})
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={feedEndRef} />
            </div>
          </div>
        )}

        {/* Live Counts Summary */}
        {totalTests > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '14px',
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
            <div style={{ padding: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '12px', color: '#D97706' }}>Blocked</div>
              <div style={{ fontSize: '20px', fontWeight: 600, marginTop: '4px', color: '#D97706' }}>{blockedCount}</div>
            </div>
            <div style={{ padding: '16px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '12px', color: '#64748B' }}>Not Run</div>
              <div style={{ fontSize: '20px', fontWeight: 600, marginTop: '4px', color: '#64748B' }}>{notRunCount}</div>
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
              {run?.status === 'QUEUED' || currentStage === 'PLANNING'
                ? 'Planning tests from your requirements...'
                : 'No test scenarios recorded for this run.'}
            </div>
          ) : (
            <div>
              {testCases.map((tc, tcIdx) => {
                const res = resultsMap[tc.id];
                const isExpanded = !!expandedTestIds[tc.id];

                const resError = res?.error_message || tc.error_message || '';
                const isNotRun =
                  res?.status === 'NOT_RUN' ||
                  tc.status === 'NOT_RUN' ||
                  resError.startsWith('Not executed:') ||
                  (isTerminal && !res && tc.status === 'PENDING');

                // Live status badge: Pending, Running, Passed, Failed, Blocked, Not Run
                const effectiveStatus = isNotRun ? 'NOT_RUN' : (res ? res.status : (tc.status || 'PENDING'));
                const testStatusStyle = getStatusStyle(effectiveStatus);
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
                    {effectiveStatus === 'NOT_RUN' ? 'Not Run' : effectiveStatus}
                  </span>
                );

                return (
                  <div
                    key={tc.id || tcIdx}
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
                          {tc.test_key || `TC-${tcIdx + 1}`}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 500 }}>{tc.title}</span>
                        {tc.priority && (
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
                        )}
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
                          <span style={{ color: '#4F46E5' }}>{tc.source_requirement || 'N/A'}</span>
                        </div>
                        {tc.description && (
                          <div style={{ marginBottom: '12px', color: '#475569' }}>
                            <strong>Description: </strong> {tc.description}
                          </div>
                        )}
                        {tc.target_role && (
                          <div style={{ marginBottom: '12px', color: '#475569' }}>
                            <strong>Target Role: </strong> {tc.target_role}
                          </div>
                        )}
                        {tc.preconditions && (
                          <div style={{ marginBottom: '12px', color: '#475569' }}>
                            <strong>Preconditions: </strong> {tc.preconditions}
                          </div>
                        )}

                        {/* Planned Checks & Verdicts */}
                        {tc.checks && tc.checks.length > 0 && (
                          <div style={{ marginBottom: '14px' }}>
                            <div style={{ fontWeight: 600, color: '#334155', marginBottom: '6px' }}>
                              Requirement Checks:
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                              {tc.checks.map((chk, cIdx) => {
                                const chkRes = (res?.check_results || tc.check_results || []).find((cr) => cr.check_id === chk.check_id);
                                const chkStatus = chkRes?.result || 'PENDING';
                                const badgeStyle = chkStatus === 'PASSED'
                                  ? { bg: '#DCFCE7', text: '#166534', border: '#86EFAC' }
                                  : chkStatus === 'FAILED'
                                  ? { bg: '#FEE2E2', text: '#991B1B', border: '#FECACA' }
                                  : chkStatus === 'INCONCLUSIVE'
                                  ? { bg: '#FEF3C7', text: '#92400E', border: '#FDE68A' }
                                  : { bg: '#F1F5F9', text: '#475569', border: '#E2E8F0' };
                                return (
                                  <div
                                    key={chk.check_id || cIdx}
                                    style={{
                                      padding: '8px 12px',
                                      backgroundColor: '#FFFFFF',
                                      border: '1px solid #E2E8F0',
                                      borderRadius: '6px',
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      fontSize: '13px',
                                    }}
                                  >
                                    <div>
                                      <span style={{ fontWeight: 500 }}>{chk.description || chk.check_id}</span>
                                      {chk.source_requirement && (
                                        <span style={{ marginLeft: '8px', fontSize: '11px', color: '#4F46E5', fontFamily: 'monospace' }}>
                                          [{chk.source_requirement}]
                                        </span>
                                      )}
                                      {chkRes?.evidence && (
                                        <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>
                                          Evidence: <em>"{chkRes.evidence}"</em>
                                        </div>
                                      )}
                                    </div>
                                    <span
                                      style={{
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        fontSize: '11px',
                                        fontWeight: 700,
                                        backgroundColor: badgeStyle.bg,
                                        color: badgeStyle.text,
                                        border: `1px solid ${badgeStyle.border}`,
                                      }}
                                    >
                                      {chkStatus}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {resError && (
                          <div
                            style={{
                              marginTop: '14px',
                              padding: '10px 14px',
                              backgroundColor: isNotRun ? '#F1F5F9' : '#FEF2F2',
                              border: `1px solid ${isNotRun ? '#CBD5E1' : '#FECACA'}`,
                              borderRadius: '6px',
                              color: isNotRun ? '#475569' : '#991B1B',
                              fontSize: '13px',
                            }}
                          >
                            <strong>Reason: </strong> {resError}
                          </div>
                        )}

                        {!res && isTerminal && !resError && (
                          <div
                            style={{
                              marginTop: '14px',
                              padding: '10px 14px',
                              backgroundColor: '#F1F5F9',
                              border: '1px solid #CBD5E1',
                              borderRadius: '6px',
                              color: '#475569',
                              fontSize: '13px',
                            }}
                          >
                            <strong>Reason: </strong> Not executed: run stopped ({run?.error_message || 'terminated early'})
                          </div>
                        )}

                        {/* Execution Details Box */}
                        {(() => {
                          const execSteps = res?.steps || tc.steps || res?.action_log || [];
                          const duration = res?.duration_seconds ?? tc.duration_seconds;
                          const finalObs = res?.final_observation || tc.final_observation || res?.observations;
                          const evidenceQuote = res?.evidence || tc.evidence;
                          const screenshotPath = res?.screenshot_path || tc.screenshot_path || (res?.evidence_paths && res.evidence_paths[0]);
                          const failureScreenshotPath = res?.failure_screenshot_path || tc.failure_screenshot_path;
                          const screenshotError = res?.screenshot_error || tc.screenshot_error;

                          return (
                            <div
                              style={{
                                marginTop: '16px',
                                padding: '14px 16px',
                                backgroundColor: '#FFFFFF',
                                borderRadius: '6px',
                                border: '1px solid #E2E8F0',
                              }}
                            >
                              <div
                                style={{
                                  fontWeight: 600,
                                  marginBottom: '10px',
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                }}
                              >
                                <span>Execution Results</span>
                                {duration !== null && duration !== undefined && (
                                  <span style={{ fontSize: '12px', fontWeight: 500, color: '#64748B' }}>
                                    Duration: {duration.toFixed(1)}s
                                  </span>
                                )}
                              </div>

                              {finalObs && (
                                <div style={{ marginBottom: '8px', color: '#334155', fontSize: '13px' }}>
                                  <strong>Final Observation: </strong> {finalObs}
                                </div>
                              )}

                              {evidenceQuote && (
                                <div style={{ marginBottom: '10px', color: '#334155', fontSize: '13px' }}>
                                  <strong>Evidence Quote: </strong> <em>"{evidenceQuote}"</em>
                                </div>
                              )}

                              {/* Step Timeline */}
                              {execSteps && execSteps.length > 0 ? (
                                <div style={{ marginTop: '12px' }}>
                                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '6px' }}>
                                    Step Timeline ({execSteps.length} steps):
                                  </div>
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {execSteps.map((step, sIdx) => {
                                      const act = step.action || step.tool || 'action';
                                      const badgeStyle = getActionBadgeStyle(act);
                                      const obsText = (step.observation || step.thought || step.error || (step.arguments ? JSON.stringify(step.arguments) : '')).slice(0, 300);
                                      return (
                                        <div
                                          key={sIdx}
                                          data-testid="step-timeline-item"
                                          style={{
                                            padding: '8px 12px',
                                            backgroundColor: '#F8FAFC',
                                            border: '1px solid #E2E8F0',
                                            borderRadius: '6px',
                                            fontSize: '12px',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: '3px',
                                          }}
                                        >
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                            <span style={{ fontWeight: 600, color: '#334155' }}>
                                              Step {step.step || sIdx + 1}:
                                            </span>
                                            <span
                                              style={{
                                                padding: '2px 8px',
                                                borderRadius: '4px',
                                                fontSize: '11px',
                                                fontWeight: 600,
                                                backgroundColor: badgeStyle.bg,
                                                color: badgeStyle.text,
                                              }}
                                            >
                                              {act}
                                            </span>
                                            {(step.selector || step.url) && (
                                              <code
                                                style={{
                                                  fontSize: '11px',
                                                  color: '#4F46E5',
                                                  backgroundColor: '#EEF2FF',
                                                  padding: '1px 6px',
                                                  borderRadius: '3px',
                                                }}
                                              >
                                                {step.selector || step.url}
                                              </code>
                                            )}
                                          </div>
                                          {obsText && (
                                            <div style={{ color: '#475569', fontSize: '12px', lineHeight: 1.4 }}>
                                              {obsText}
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              ) : (
                                <div
                                  data-testid="no-steps-message"
                                  style={{
                                    marginTop: '8px',
                                    padding: '10px 12px',
                                    backgroundColor: '#F8FAFC',
                                    border: '1px solid #E2E8F0',
                                    borderRadius: '6px',
                                    color: '#64748B',
                                    fontSize: '13px',
                                  }}
                                >
                                  No steps recorded for this test ({res?.error_message || tc.error_message || (!res && isTerminal ? 'run terminated before executing this scenario' : 'scenario concluded without recorded steps')}).
                                </div>
                              )}

                              {/* Screenshot Thumbnail */}
                              {(screenshotPath || failureScreenshotPath || screenshotError) && (
                                <div style={{ marginTop: '14px' }}>
                                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '6px' }}>
                                    Screenshot Evidence:
                                  </div>
                                  <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                                    {failureScreenshotPath && (
                                      <div>
                                        <div style={{ fontSize: '11px', color: '#DC2626', fontWeight: 600, marginBottom: '4px' }}>
                                          Failure Moment:
                                        </div>
                                        <ScreenshotViewer
                                          runId={runId}
                                          filename={failureScreenshotPath.split(/[\\/]/).pop()}
                                          caption={`Failure Moment ${tc.test_key || tc.title}`}
                                          reason={screenshotError}
                                        />
                                      </div>
                                    )}
                                    {screenshotPath && (
                                      <div>
                                        <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 600, marginBottom: '4px' }}>
                                          Final State:
                                        </div>
                                        <ScreenshotViewer
                                          runId={runId}
                                          filename={screenshotPath.split(/[\\/]/).pop()}
                                          caption={`Evidence ${tc.test_key || tc.title}`}
                                          reason={screenshotError}
                                        />
                                      </div>
                                    )}
                                    {!failureScreenshotPath && !screenshotPath && (
                                      <ScreenshotViewer
                                        runId={runId}
                                        filename={null}
                                        reason={screenshotError}
                                      />
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })()}
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
