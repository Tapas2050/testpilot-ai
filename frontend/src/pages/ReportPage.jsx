import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { ScreenshotViewer } from '../components/ScreenshotViewer';
import { Banner } from '../components/Banner';
import { getSeverityStyle } from '../utils/statusStyles';

const ACTION_BADGES = {
  click: { bg: '#E0F2FE', text: '#0369A1' },
  fill: { bg: '#FEF3C7', text: '#B45309' },
  navigate: { bg: '#F3E8FF', text: '#6B21A8' },
  press_key: { bg: '#EDE9FE', text: '#5B21B6' },
  select: { bg: '#CCFBF1', text: '#0F766E' },
  finish: { bg: '#DCFCE7', text: '#15803D' },
  login: { bg: '#FEE2E2', text: '#B91C1C' },
  loop_detected: { bg: '#FEE2E2', text: '#B91C1C' },
};

function getActionBadgeStyle(action) {
  const key = (action || '').toLowerCase();
  return ACTION_BADGES[key] || { bg: '#F1F5F9', text: '#475569' };
}

export function ReportPage() {
  const { id: runId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPassedTests, setShowPassedTests] = useState(false);
  const [expandedFailureIds, setExpandedFailureIds] = useState({});
  const [expandedPassedIds, setExpandedPassedIds] = useState({});

  useEffect(() => {
    let active = true;

    async function fetchReport() {
      try {
        setLoading(true);
        const data = await api.runs.report(runId);
        if (!active) return;
        setReport(data);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err.message || 'Failed to load test run report');
      } finally {
        if (active) setLoading(false);
      }
    }

    if (runId) {
      fetchReport();
    }

    return () => {
      active = false;
    };
  }, [runId]);

  if (loading) {
    return (
      <div style={{ padding: '60px', maxWidth: '1000px', margin: '0 auto', textAlign: 'center', color: '#64748B' }}>
        Loading comprehensive test report...
      </div>
    );
  }

  if (error || !report) {
    return (
      <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto' }}>
        <Banner type="error" title="Report Unavailable" message={error || 'Could not find report for this run.'} />
        <Link to="/" style={{ color: '#4F46E5', textDecoration: 'none', fontWeight: 500 }}>
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  const {
    total_tests = 0,
    passed_tests = 0,
    failed_tests = 0,
    pass_percentage = 0,
    summary = '',
    classification_breakdown = {},
    severity_breakdown = {},
    failures = [],
    test_cases = [],
    results = [],
    generated_at = '',
  } = report;

  const passedCases = test_cases.filter((tc) => {
    const res = results.find((r) => r.test_case_id === tc.id);
    return res && res.status === 'PASSED';
  });

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#FFFFFF', color: '#0F172A', paddingBottom: '80px' }}>
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
          <Link to={`/runs/${runId}`} style={{ color: '#64748B', textDecoration: 'none' }}>
            Run #{runId?.slice(0, 8)}
          </Link>
          <span>/</span>
          <span style={{ color: '#0F172A', fontWeight: 500 }}>Report</span>
        </div>
      </header>

      <main style={{ maxWidth: '1000px', margin: '0 auto', padding: '32px 24px' }}>
        {/* Title and Timestamp */}
        <div style={{ marginBottom: '28px' }}>
          <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 6px 0' }}>
            Test Run Executive Report
          </h1>
          <div style={{ fontSize: '13px', color: '#64748B' }}>
            Run ID: <span style={{ fontFamily: 'monospace' }}>{runId}</span> • Generated:{' '}
            {generated_at ? new Date(generated_at).toLocaleString() : 'Just now'}
          </div>
        </div>

        {/* Stat Tiles */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            marginBottom: '28px',
          }}
        >
          <div
            data-testid="stat-total"
            style={{ padding: '20px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}
          >
            <div style={{ fontSize: '13px', color: '#64748B', fontWeight: 500 }}>Total Tests</div>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#0F172A', marginTop: '6px' }}>
              {total_tests}
            </div>
          </div>

          <div
            data-testid="stat-passed"
            style={{ padding: '20px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}
          >
            <div style={{ fontSize: '13px', color: '#16A34A', fontWeight: 500 }}>Passed Tests</div>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#16A34A', marginTop: '6px' }}>
              {passed_tests}
            </div>
          </div>

          <div
            data-testid="stat-failed"
            style={{ padding: '20px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}
          >
            <div style={{ fontSize: '13px', color: '#DC2626', fontWeight: 500 }}>Failed Tests</div>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#DC2626', marginTop: '6px' }}>
              {failed_tests}
            </div>
          </div>

          <div
            data-testid="stat-pass-rate"
            style={{ padding: '20px', backgroundColor: '#F8FAFC', borderRadius: '8px', border: '1px solid #E2E8F0' }}
          >
            <div style={{ fontSize: '13px', color: '#4F46E5', fontWeight: 500 }}>Pass Rate</div>
            <div style={{ fontSize: '28px', fontWeight: 700, color: '#4F46E5', marginTop: '6px' }}>
              {pass_percentage}%
            </div>
          </div>
        </div>

        {/* AI Analysis Summary */}
        <div
          data-testid="ai-summary"
          style={{
            padding: '20px',
            borderRadius: '8px',
            backgroundColor: '#EFF6FF',
            border: '1px solid #BFDBFE',
            marginBottom: '28px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ fontSize: '14px', fontWeight: 600, color: '#1E3A8A' }}>
              AI Executive Summary
            </div>
            {report?.live_llm_calls !== undefined && (
              <span
                data-testid="live-llm-calls-badge"
                style={{
                  fontSize: '12px',
                  fontWeight: 600,
                  backgroundColor: '#DBEAFE',
                  color: '#1E40AF',
                  padding: '2px 8px',
                  borderRadius: '12px',
                }}
              >
                Live LLM Calls: {report.live_llm_calls}
              </span>
            )}
          </div>
          <div style={{ fontSize: '14px', color: '#1E40AF', lineHeight: 1.6 }}>{summary}</div>
        </div>

        {/* Severity & Classification Breakdown */}
        {failed_tests > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '20px',
              marginBottom: '32px',
            }}
          >
            <div style={{ padding: '20px', border: '1px solid #E2E8F0', borderRadius: '8px', backgroundColor: '#FFFFFF' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '12px' }}>
                Severity Breakdown
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {Object.entries(severity_breakdown).map(([sev, count]) => {
                  const style = getSeverityStyle(sev);
                  return (
                    <div
                      key={sev}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        backgroundColor: style.bg,
                        color: style.text,
                        border: `1px solid ${style.border}`,
                        fontSize: '12px',
                        fontWeight: 600,
                      }}
                    >
                      {sev}: {count}
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ padding: '20px', border: '1px solid #E2E8F0', borderRadius: '8px', backgroundColor: '#FFFFFF' }}>
              <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '12px' }}>
                Classification Breakdown
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {Object.entries(classification_breakdown).map(([cls, count]) => (
                  <div
                    key={cls}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      backgroundColor: '#F8FAFC',
                      color: '#0F172A',
                      border: '1px solid #CBD5E1',
                      fontSize: '12px',
                      fontWeight: 600,
                    }}
                  >
                    {cls}: {count}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Failure Findings */}
        <section style={{ marginBottom: '36px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>
            Defect & Failure Analysis ({failures.length})
          </h2>

          {failures.length === 0 ? (
            <div
              style={{
                padding: '32px',
                textAlign: 'center',
                backgroundColor: '#F8FAFC',
                borderRadius: '8px',
                border: '1px solid #E2E8F0',
                color: '#64748B',
              }}
            >
              All tests passed. No failures to show.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {failures.map((f, idx) => {
                const sevStyle = getSeverityStyle(f.severity);

                // Find matching test case and result for title and evidence screenshots
                const matchedResult = results.find(
                  (r) =>
                    (f.test_case_id && (r.test_case_id === f.test_case_id || r.id === f.test_case_id)) ||
                    (f.test_result_id && r.id === f.test_result_id)
                );
                const matchedTestCase = test_cases.find(
                  (tc) =>
                    (f.test_case_id && tc.id === f.test_case_id) ||
                    (matchedResult && tc.id === matchedResult.test_case_id)
                );

                const evidencePaths = matchedResult?.evidence_paths || [];
                const screenshotPath =
                  f.screenshot_path ||
                  matchedResult?.screenshot_path ||
                  matchedTestCase?.screenshot_path ||
                  (evidencePaths.length > 0 ? evidencePaths[0] : null);
                const failureScreenshotPath =
                  f.failure_screenshot_path ||
                  matchedResult?.failure_screenshot_path ||
                  matchedTestCase?.failure_screenshot_path ||
                  null;
                const screenshotError =
                  f.screenshot_error ||
                  matchedResult?.screenshot_error ||
                  matchedTestCase?.screenshot_error ||
                  null;

                const cardId = f.id || idx;
                const isExpanded = !!expandedFailureIds[cardId];
                const execSteps = matchedResult?.steps || matchedTestCase?.steps || [];
                const duration = matchedResult?.duration_seconds ?? matchedTestCase?.duration_seconds;
                const finalObs = matchedResult?.final_observation || f.final_observation || f.observed || f.observed_behavior;
                const evidenceQuote = matchedResult?.evidence || f.evidence || matchedTestCase?.evidence;
                const checks = matchedTestCase?.checks || f.checks || [];
                const checkResults = matchedResult?.check_results || f.check_results || [];

                return (
                  <div
                    key={cardId}
                    data-testid="failure-card"
                    style={{
                      border: '1px solid #E2E8F0',
                      borderRadius: '8px',
                      padding: '20px',
                      backgroundColor: '#FFFFFF',
                      boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.05)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '12px',
                        flexWrap: 'wrap',
                        gap: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 700,
                            backgroundColor: sevStyle.bg,
                            color: sevStyle.text,
                            border: `1px solid ${sevStyle.border}`,
                          }}
                        >
                          {f.severity}
                        </span>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: 600,
                            backgroundColor: '#F1F5F9',
                            color: '#0F172A',
                          }}
                        >
                          {f.classification}
                        </span>
                        {f.confidence !== undefined && (
                          <span style={{ fontSize: '12px', color: '#64748B' }}>
                            Confidence: {Math.round(f.confidence * 100)}%
                          </span>
                        )}
                      </div>

                      {matchedTestCase && (
                        <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#4F46E5', fontWeight: 600 }}>
                          {matchedTestCase.test_key || 'TC'}: {matchedTestCase.title}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '14px' }}>
                      <div style={{ backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '6px', fontSize: '13px' }}>
                        <strong style={{ color: '#166534', display: 'block', marginBottom: '4px' }}>
                          Expected Behavior:
                        </strong>
                        <span style={{ color: '#334155' }}>{f.expected || f.expected_behavior}</span>
                      </div>
                      <div style={{ backgroundColor: '#FEF2F2', padding: '12px', borderRadius: '6px', fontSize: '13px' }}>
                        <strong style={{ color: '#991B1B', display: 'block', marginBottom: '4px' }}>
                          Observed Behavior:
                        </strong>
                        <span style={{ color: '#7F1D1D' }}>{f.observed || f.observed_behavior}</span>
                      </div>
                    </div>

                    <div style={{ fontSize: '13px', lineHeight: 1.5, marginBottom: '12px', color: '#1E293B' }}>
                      <strong>Root Cause Explanation: </strong>
                      {f.explanation}
                    </div>

                    {f.suggested_action && (
                      <div
                        style={{
                          fontSize: '13px',
                          lineHeight: 1.5,
                          padding: '10px 14px',
                          backgroundColor: '#F0FDF4',
                          borderRadius: '6px',
                          border: '1px solid #BBF7D0',
                          color: '#166534',
                          marginBottom: '12px',
                        }}
                      >
                        <strong>Suggested Engineering Action: </strong>
                        {f.suggested_action}
                      </div>
                    )}

                    {(screenshotPath || failureScreenshotPath || screenshotError) && (
                      <div style={{ marginTop: '12px', marginBottom: '12px' }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '6px' }}>
                          Evidence Screenshots:
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
                                caption={`Failure Moment ${f.classification}`}
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
                                caption={`Failure Evidence ${f.classification}`}
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

                    {/* Expandable Execution Details Toggle */}
                    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid #F1F5F9' }}>
                      <button
                        type="button"
                        onClick={() => setExpandedFailureIds((prev) => ({ ...prev, [cardId]: !prev[cardId] }))}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#4F46E5',
                          fontSize: '13px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          padding: 0,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>{isExpanded ? 'Hide Execution Details ▲' : 'Show Execution Details ▼'}</span>
                        {duration !== null && duration !== undefined && (
                          <span style={{ color: '#64748B', fontWeight: 400, fontSize: '12px' }}>
                            ({duration.toFixed(1)}s)
                          </span>
                        )}
                      </button>

                      {isExpanded && (
                        <div
                          style={{
                            marginTop: '12px',
                            padding: '14px',
                            backgroundColor: '#F8FAFC',
                            borderRadius: '6px',
                            border: '1px solid #E2E8F0',
                          }}
                        >
                          {/* Requirement Checks */}
                          {checks && checks.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                              <div style={{ fontWeight: 600, color: '#334155', fontSize: '12px', marginBottom: '6px' }}>
                                Requirement Checks:
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                {checks.map((chk, cIdx) => {
                                  const chkRes = checkResults.find((cr) => cr.check_id === chk.check_id);
                                  const chkStatus = chkRes?.result || 'PENDING';
                                  return (
                                    <div
                                      key={chk.check_id || cIdx}
                                      style={{
                                        padding: '6px 10px',
                                        backgroundColor: '#FFFFFF',
                                        border: '1px solid #E2E8F0',
                                        borderRadius: '4px',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        fontSize: '12px',
                                      }}
                                    >
                                      <span>{chk.description || chk.check_id}</span>
                                      <span
                                        style={{
                                          padding: '1px 6px',
                                          borderRadius: '3px',
                                          fontSize: '11px',
                                          fontWeight: 700,
                                          backgroundColor: chkStatus === 'PASSED' ? '#DCFCE7' : '#FEE2E2',
                                          color: chkStatus === 'PASSED' ? '#166534' : '#991B1B',
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

                          {finalObs && (
                            <div style={{ marginBottom: '8px', color: '#334155', fontSize: '13px' }}>
                              <strong>Final Observation: </strong> {finalObs}
                            </div>
                          )}

                          {evidenceQuote && (
                            <div style={{ marginBottom: '8px', color: '#334155', fontSize: '13px' }}>
                              <strong>Evidence Quote: </strong> <em>"{evidenceQuote}"</em>
                            </div>
                          )}

                          {/* Step Timeline */}
                          {execSteps && execSteps.length > 0 ? (
                            <div style={{ marginTop: '10px' }}>
                              <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '6px' }}>
                                Step Timeline ({execSteps.length} steps):
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                {execSteps.map((step, sIdx) => {
                                  const act = step.action || step.tool || 'action';
                                  const badge = getActionBadgeStyle(act);
                                  const obsText = (
                                    step.observation ||
                                    step.thought ||
                                    step.error ||
                                    (step.arguments ? JSON.stringify(step.arguments) : '')
                                  ).slice(0, 300);
                                  return (
                                    <div
                                      key={sIdx}
                                      data-testid="step-timeline-item"
                                      style={{
                                        padding: '8px 12px',
                                        backgroundColor: '#FFFFFF',
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
                                            backgroundColor: badge.bg,
                                            color: badge.text,
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
                                backgroundColor: '#FFFFFF',
                                border: '1px solid #E2E8F0',
                                borderRadius: '6px',
                                color: '#64748B',
                                fontSize: '13px',
                              }}
                            >
                              No steps recorded for this test ({f.explanation || matchedResult?.error_message || 'scenario concluded without recorded steps'}).
                            </div>
                          )}

                          {/* Screenshot */}
                          {(screenshotPath || failureScreenshotPath || screenshotError) && (
                            <div style={{ marginTop: '12px' }}>
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
                                      caption={`Failure Moment ${f.classification}`}
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
                                      caption={`Failure Evidence ${f.classification}`}
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
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Collapsible Passed Tests */}
        {passedCases.length > 0 && (
          <section style={{ border: '1px solid #E2E8F0', borderRadius: '8px', overflow: 'hidden' }}>
            <div
              onClick={() => setShowPassedTests(!showPassedTests)}
              style={{
                padding: '16px 20px',
                backgroundColor: '#F8FAFC',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '14px', color: '#16A34A' }}>
                ✓ Passed Scenarios ({passedCases.length})
              </div>
              <span style={{ color: '#64748B', fontSize: '12px' }}>
                {showPassedTests ? 'Hide ▲' : 'Show ▼'}
              </span>
            </div>

            {showPassedTests && (
              <div style={{ padding: '0 20px', backgroundColor: '#FFFFFF' }}>
                {passedCases.map((tc) => {
                  const res = results.find((r) => r.test_case_id === tc.id || r.id === tc.id);
                  const isExpanded = !!expandedPassedIds[tc.id];
                  const execSteps = res?.steps || tc.steps || [];
                  const duration = res?.duration_seconds ?? tc.duration_seconds;
                  const finalObs = res?.final_observation || tc.final_observation;
                  const evidenceQuote = res?.evidence || tc.evidence;
                  const ssPath = res?.screenshot_path || tc.screenshot_path;
                  const failureSsPath = res?.failure_screenshot_path || tc.failure_screenshot_path;
                  const ssError = res?.screenshot_error || tc.screenshot_error;
                  const checks = tc.checks || [];
                  const checkResults = res?.check_results || tc.check_results || [];

                  return (
                    <div
                      key={tc.id}
                      style={{
                        padding: '12px 0',
                        borderBottom: '1px solid #F1F5F9',
                        fontSize: '13px',
                      }}
                    >
                      <div
                        onClick={() => setExpandedPassedIds((prev) => ({ ...prev, [tc.id]: !prev[tc.id] }))}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          cursor: 'pointer',
                        }}
                      >
                        <div>
                          <span style={{ fontFamily: 'monospace', color: '#4F46E5', marginRight: '8px' }}>
                            {tc.test_key || 'TC'}
                          </span>
                          <span style={{ fontWeight: 500 }}>{tc.title}</span>
                          {duration !== null && duration !== undefined && (
                            <span style={{ marginLeft: '10px', color: '#64748B', fontSize: '12px' }}>
                              ({duration.toFixed(1)}s)
                            </span>
                          )}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              backgroundColor: '#DCFCE7',
                              color: '#166534',
                              fontSize: '11px',
                              fontWeight: 600,
                            }}
                          >
                            PASSED
                          </span>
                          <span style={{ color: '#94A3B8', fontSize: '11px' }}>
                            {isExpanded ? '▲' : '▼'}
                          </span>
                        </div>
                      </div>

                      {isExpanded && (
                        <div
                          style={{
                            marginTop: '10px',
                            padding: '12px',
                            backgroundColor: '#F8FAFC',
                            borderRadius: '6px',
                            border: '1px solid #E2E8F0',
                          }}
                        >
                          {checks && checks.length > 0 && (
                            <div style={{ marginBottom: '10px' }}>
                              <div style={{ fontWeight: 600, color: '#334155', fontSize: '12px', marginBottom: '4px' }}>
                                Requirement Checks:
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                {checks.map((chk, cIdx) => {
                                  const chkRes = checkResults.find((cr) => cr.check_id === chk.check_id);
                                  const chkStatus = chkRes?.result || 'PASSED';
                                  return (
                                    <div
                                      key={chk.check_id || cIdx}
                                      style={{
                                        padding: '4px 8px',
                                        backgroundColor: '#FFFFFF',
                                        border: '1px solid #E2E8F0',
                                        borderRadius: '4px',
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        fontSize: '12px',
                                      }}
                                    >
                                      <span>{chk.description || chk.check_id}</span>
                                      <span style={{ color: '#166534', fontWeight: 600 }}>{chkStatus}</span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {finalObs && (
                            <div style={{ marginBottom: '6px', color: '#334155' }}>
                              <strong>Final Observation: </strong> {finalObs}
                            </div>
                          )}
                          {evidenceQuote && (
                            <div style={{ marginBottom: '6px', color: '#334155' }}>
                              <strong>Evidence Quote: </strong> <em>"{evidenceQuote}"</em>
                            </div>
                          )}

                          {execSteps && execSteps.length > 0 ? (
                            <div style={{ marginTop: '8px' }}>
                              <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
                                Step Timeline ({execSteps.length} steps):
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                {execSteps.map((step, sIdx) => {
                                  const act = step.action || step.tool || 'action';
                                  const badge = getActionBadgeStyle(act);
                                  const obs = (step.observation || step.thought || '').slice(0, 300);
                                  return (
                                    <div
                                      key={sIdx}
                                      style={{
                                        padding: '6px 10px',
                                        backgroundColor: '#FFFFFF',
                                        border: '1px solid #E2E8F0',
                                        borderRadius: '4px',
                                        fontSize: '12px',
                                      }}
                                    >
                                      <span style={{ fontWeight: 600 }}>Step {step.step || sIdx + 1}: </span>
                                      <span
                                        style={{
                                          padding: '1px 6px',
                                          borderRadius: '3px',
                                          backgroundColor: badge.bg,
                                          color: badge.text,
                                          fontSize: '11px',
                                          fontWeight: 600,
                                          marginRight: '6px',
                                        }}
                                      >
                                        {act}
                                      </span>
                                      {(step.selector || step.url) && (
                                        <code style={{ fontSize: '11px', color: '#4F46E5', marginRight: '6px' }}>
                                          {step.selector || step.url}
                                        </code>
                                      )}
                                      {obs && <span style={{ color: '#64748B' }}>{obs}</span>}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ) : (
                            <div
                              data-testid="no-steps-message"
                              style={{ color: '#64748B', fontSize: '12px', padding: '6px 0' }}
                            >
                              No steps recorded for this test.
                            </div>
                          )}

                          {(ssPath || failureSsPath || ssError) && (
                            <div style={{ marginTop: '10px' }}>
                              <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '4px' }}>
                                Screenshot Evidence:
                              </div>
                              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                                {failureSsPath && (
                                  <div>
                                    <div style={{ fontSize: '11px', color: '#DC2626', fontWeight: 600, marginBottom: '2px' }}>
                                      Failure Moment:
                                    </div>
                                    <ScreenshotViewer
                                      runId={runId}
                                      filename={failureSsPath.split(/[\\/]/).pop()}
                                      caption={`Failure Moment for ${tc.title}`}
                                      reason={ssError}
                                    />
                                  </div>
                                )}
                                {ssPath && (
                                  <div>
                                    <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 600, marginBottom: '2px' }}>
                                      Final State:
                                    </div>
                                    <ScreenshotViewer
                                      runId={runId}
                                      filename={ssPath.split(/[\\/]/).pop()}
                                      caption={`Evidence for ${tc.title}`}
                                      reason={ssError}
                                    />
                                  </div>
                                )}
                                {!failureSsPath && !ssPath && (
                                  <ScreenshotViewer
                                    runId={runId}
                                    filename={null}
                                    reason={ssError}
                                  />
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
