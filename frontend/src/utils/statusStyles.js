/**
 * Shared status and severity color and styling definitions.
 * Provides safe lookups with neutral fallbacks to prevent undefined crashes.
 */

export const STATUS_STYLES = {
  // Run-level lifecycle statuses & agent stages
  QUEUED: { bg: '#FEF3C7', text: '#92400E', border: '#FCD34D', badgeClass: 'badge-warning', label: 'Queued' },
  PLANNING: { bg: '#DBEAFE', text: '#1E40AF', border: '#93C5FD', badgeClass: 'badge-info', label: 'Planning' },
  EXECUTING: { bg: '#DBEAFE', text: '#1E40AF', border: '#93C5FD', badgeClass: 'badge-info', label: 'Executing' },
  ANALYZING: { bg: '#EDE9FE', text: '#5B21B6', border: '#C4B5FD', badgeClass: 'badge-info', label: 'Analyzing' },
  REPORTING: { bg: '#E0F2FE', text: '#0369A1', border: '#7DD3FC', badgeClass: 'badge-info', label: 'Reporting' },
  RUNNING: { bg: '#DBEAFE', text: '#1E40AF', border: '#93C5FD', badgeClass: 'badge-info', label: 'Running' },
  COMPLETED: { bg: '#DCFCE7', text: '#166534', border: '#86EFAC', badgeClass: 'badge-pass', label: 'Completed' },
  FAILED: { bg: '#FEE2E2', text: '#991B1B', border: '#FCA5A5', badgeClass: 'badge-fail', label: 'Failed' },
  CANCELLED: { bg: '#F1F5F9', text: '#475569', border: '#CBD5E1', badgeClass: 'badge-secondary', label: 'Cancelled' },

  // Per-test scenario statuses
  PENDING: { bg: '#F1F5F9', text: '#64748B', border: '#CBD5E1', badgeClass: 'badge-secondary', label: 'Pending' },
  PASSED: { bg: '#DCFCE7', text: '#166534', border: '#86EFAC', badgeClass: 'badge-pass', label: 'Passed' },
  BLOCKED: { bg: '#FEF3C7', text: '#92400E', border: '#FCD34D', badgeClass: 'badge-warning', label: 'Blocked' },
};

export const DEFAULT_STATUS_STYLE = {
  bg: '#F1F5F9',
  text: '#475569',
  border: '#CBD5E1',
  badgeClass: 'badge-secondary',
  label: 'Unknown',
};

/**
 * Returns a complete style object for any status with neutral fallback.
 * Guaranteed to return an object with { bg, text, border, badgeClass, label }.
 */
export function getStatusStyle(status) {
  if (!status || typeof status !== 'string') {
    return DEFAULT_STATUS_STYLE;
  }
  const normalized = status.toUpperCase().trim();
  const matched = STATUS_STYLES[normalized];
  if (matched) {
    return matched;
  }
  return {
    ...DEFAULT_STATUS_STYLE,
    label: status,
  };
}

export const SEVERITY_STYLES = {
  CRITICAL: { bg: '#FEE2E2', text: '#991B1B', border: '#F87171' },
  HIGH: { bg: '#FFEDD5', text: '#9A3412', border: '#FB923C' },
  MEDIUM: { bg: '#FEF3C7', text: '#92400E', border: '#FCD34D' },
  LOW: { bg: '#F1F5F9', text: '#475569', border: '#CBD5E1' },
};

export const DEFAULT_SEVERITY_STYLE = {
  bg: '#F1F5F9',
  text: '#475569',
  border: '#CBD5E1',
};

/**
 * Returns severity styling with neutral fallback.
 * Guaranteed to return an object with { bg, text, border }.
 */
export function getSeverityStyle(severity) {
  if (!severity || typeof severity !== 'string') {
    return DEFAULT_SEVERITY_STYLE;
  }
  const normalized = severity.toUpperCase().trim();
  return SEVERITY_STYLES[normalized] || DEFAULT_SEVERITY_STYLE;
}
