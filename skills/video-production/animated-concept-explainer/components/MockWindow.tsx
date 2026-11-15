import React from 'react';

export interface MockWindowProps {
  title?: string;
  url?: string;
  width?: number | string;
  height?: number | string;
  variant?: 'app' | 'browser' | 'terminal';
  glow?: boolean;
  accentColor?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const MockWindow: React.FC<MockWindowProps> = ({
  title = 'app.tsx',
  url,
  width = 960,
  height = 540,
  variant = 'app',
  glow = false,
  accentColor = '#8B5CF6',
  children,
  style,
}) => {
  return (
    <div
      style={{
        width,
        height,
        backgroundColor: '#14161E',
        borderRadius: 16,
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: glow
          ? `0 24px 60px -12px rgba(0, 0, 0, 0.75), 0 0 40px -10px ${accentColor}25`
          : '0 24px 60px -12px rgba(0, 0, 0, 0.65)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
        boxSizing: 'border-box',
        ...style,
      }}
    >
      {/* Window Header Bar */}
      <div
        style={{
          height: 42,
          backgroundColor: '#1B1E29',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: 16,
          userSelect: 'none',
        }}
      >
        {/* macOS Traffic Lights */}
        <div style={{ display: 'flex', gap: 7, alignItems: 'center' }}>
          <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: '#FF5F56' }} />
          <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: '#FFBD2E' }} />
          <div style={{ width: 11, height: 11, borderRadius: '50%', backgroundColor: '#27C93F' }} />
        </div>

        {/* Center: Title or URL chip */}
        <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          {variant === 'browser' || url ? (
            <div
              style={{
                backgroundColor: 'rgba(0, 0, 0, 0.35)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: 6,
                padding: '3px 20px',
                fontSize: 12,
                color: 'rgba(255, 255, 255, 0.65)',
                fontFamily: 'monospace',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span style={{ opacity: 0.5 }}>🔒</span>
              {url || 'yourapp.com'}
            </div>
          ) : (
            <span
              style={{
                fontSize: 12,
                color: 'rgba(255, 255, 255, 0.60)',
                fontFamily: 'system-ui, -apple-system, sans-serif',
                fontWeight: 500,
              }}
            >
              {title}
            </span>
          )}
        </div>

        {/* Right side placeholder to keep title centered */}
        <div style={{ width: 44 }} />
      </div>

      {/* Main Content Viewport */}
      <div
        style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {children}
      </div>
    </div>
  );
};
