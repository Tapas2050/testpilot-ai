import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { ScreenshotViewer } from '../components/ScreenshotViewer';
import { Banner } from '../components/Banner';
import { getSeverityStyle } from '../utils/statusStyles';

export function ReportPage() {
  const { id: runId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPassedTests, setShowPassedTests] = useState(false);

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
          <div style={{ fontSize: '14px', fontWeight: 600, color: '#1E3A8A', marginBottom: '8px' }}>
            AI Executive Summary
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
                const matchedResult = results.find((r) => r.id === f.test_result_id);
                const matchedTestCase = matchedResult
                  ? test_cases.find((tc) => tc.id === matchedResult.test_case_id)
                  : null;

                const evidencePaths = matchedResult?.evidence_paths || [];

                return (
                  <div
                    key={f.id || idx}
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
                          {matchedTestCase.test_key}: {matchedTestCase.title}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '14px' }}>
                      <div style={{ backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '6px', fontSize: '13px' }}>
                        <strong style={{ color: '#166534', display: 'block', marginBottom: '4px' }}>
                          Expected Behavior:
                        </strong>
                        <span style={{ color: '#334155' }}>{f.expected_behavior}</span>
                      </div>
                      <div style={{ backgroundColor: '#FEF2F2', padding: '12px', borderRadius: '6px', fontSize: '13px' }}>
                        <strong style={{ color: '#991B1B', display: 'block', marginBottom: '4px' }}>
                          Observed Behavior:
                        </strong>
                        <span style={{ color: '#7F1D1D' }}>{f.observed_behavior}</span>
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

                    {evidencePaths.length > 0 && (
                      <div style={{ marginTop: '12px' }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#64748B', marginBottom: '6px' }}>
                          Evidence Screenshots:
                        </div>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          {evidencePaths.map((p, pIdx) => {
                            const filename = p.split(/[\\/]/).pop();
                            return (
                              <ScreenshotViewer
                                key={pIdx}
                                runId={runId}
                                filename={filename}
                                caption={`Failure Evidence ${f.classification}`}
                              />
                            );
                          })}
                        </div>
                      </div>
                    )}
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
                {passedCases.map((tc) => (
                  <div
                    key={tc.id}
                    style={{
                      padding: '12px 0',
                      borderBottom: '1px solid #F1F5F9',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: '13px',
                    }}
                  >
                    <div>
                      <span style={{ fontFamily: 'monospace', color: '#4F46E5', marginRight: '8px' }}>
                        {tc.test_key}
                      </span>
                      <span>{tc.title}</span>
                    </div>
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
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
