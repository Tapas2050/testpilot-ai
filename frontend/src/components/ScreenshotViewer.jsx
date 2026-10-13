import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

export function ScreenshotViewer({
  runId,
  filename,
  screenshotPath,
  reason = null,
  caption = 'Screenshot Evidence',
}) {
  let effectiveRunId = runId;
  let effectiveFilename = filename;
  if (!effectiveRunId && screenshotPath) {
    const parts = screenshotPath.split(/[\\/]/).filter(Boolean);
    if (parts.length >= 2) {
      effectiveFilename = parts[parts.length - 1];
      effectiveRunId = parts[parts.length - 2];
    }
  }

  const [imageUrl, setImageUrl] = useState(null);
  const [loading, setLoading] = useState(!!(effectiveRunId && effectiveFilename));
  const [error, setError] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = null;

    if (!effectiveRunId || !effectiveFilename) {
      setLoading(false);
      return;
    }

    async function loadScreenshot() {
      try {
        setLoading(true);
        setError(false);
        const blob = await api.runs.fetchScreenshotBlob(effectiveRunId, effectiveFilename);
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
      } catch {
        if (!active) return;
        setError(true);
        setImageUrl(null);
      } finally {
        if (active) setLoading(false);
      }
    }

    loadScreenshot();

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [effectiveRunId, effectiveFilename]);

  if (loading) {
    return (
      <div
        data-testid="screenshot-placeholder"
        style={{
          width: '120px',
          height: '80px',
          backgroundColor: '#F1F5F9',
          border: '1px solid #E2E8F0',
          borderRadius: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '11px',
          color: '#94A3B8',
        }}
      >
        Loading...
      </div>
    );
  }

  if (!effectiveFilename) {
    return (
      <div
        data-testid="screenshot-missing"
        style={{
          minWidth: '140px',
          maxWidth: '220px',
          padding: '8px 12px',
          backgroundColor: '#F8FAFC',
          border: '1px dashed #CBD5E1',
          borderRadius: '6px',
          fontSize: '11px',
          color: '#64748B',
          lineHeight: '1.4',
        }}
      >
        <div>No screenshot was captured for this test</div>
        {reason && (
          <div style={{ fontSize: '10px', color: '#94A3B8', marginTop: '2px' }}>
            {reason}
          </div>
        )}
      </div>
    );
  }

  if (error || !imageUrl) {
    return (
      <div
        data-testid="screenshot-error"
        style={{
          minWidth: '140px',
          maxWidth: '220px',
          padding: '8px 12px',
          backgroundColor: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: '6px',
          fontSize: '11px',
          color: '#991B1B',
          lineHeight: '1.4',
        }}
      >
        <div>No screenshot was captured for this test</div>
        {reason ? (
          <div style={{ fontSize: '10px', color: '#B91C1C', marginTop: '2px' }}>
            {reason}
          </div>
        ) : (
          <div style={{ fontSize: '10px', color: '#B91C1C', marginTop: '2px' }}>
            File missing or request failed
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      <div
        onClick={() => setIsOpen(true)}
        style={{
          cursor: 'pointer',
          display: 'inline-block',
          position: 'relative',
          borderRadius: '6px',
          overflow: 'hidden',
          border: '1px solid #CBD5E1',
          transition: 'transform 0.15s ease, box-shadow 0.15s ease',
        }}
        title="Click to view full screenshot"
      >
        <img
          src={imageUrl}
          alt={caption}
          data-testid="screenshot-thumbnail"
          style={{
            width: '120px',
            height: '80px',
            objectFit: 'cover',
            display: 'block',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.75)',
            color: '#FFFFFF',
            fontSize: '10px',
            padding: '2px 4px',
            textAlign: 'center',
            textOverflow: 'ellipsis',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
          }}
        >
          {filename}
        </div>
      </div>

      {isOpen && (
        <div
          data-testid="screenshot-modal-backdrop"
          onClick={() => setIsOpen(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '24px',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '8px',
              maxWidth: '90vw',
              maxHeight: '90vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.3)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px 16px',
                borderBottom: '1px solid #E2E8F0',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '14px', color: '#0F172A' }}>
                {caption} - <span style={{ color: '#64748B', fontFamily: 'monospace' }}>{filename}</span>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '18px',
                  cursor: 'pointer',
                  color: '#64748B',
                  padding: '4px 8px',
                }}
              >
                ✕
              </button>
            </div>
            <div style={{ padding: '16px', overflow: 'auto', textAlign: 'center' }}>
              <img
                src={imageUrl}
                alt={caption}
                data-testid="screenshot-full"
                style={{
                  maxWidth: '100%',
                  maxHeight: '75vh',
                  objectFit: 'contain',
                  borderRadius: '4px',
                  border: '1px solid #E2E8F0',
                }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default ScreenshotViewer;
