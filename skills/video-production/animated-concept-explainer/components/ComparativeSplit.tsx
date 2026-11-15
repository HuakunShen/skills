import React from 'react';

export interface ComparativeSide {
  label: string;
  isCorrect?: boolean;
  content: React.ReactNode;
}

export interface ComparativeSplitProps {
  left: ComparativeSide;
  right: ComparativeSide;
  width?: number | string;
  height?: number | string;
}

export const ComparativeSplit: React.FC<ComparativeSplitProps> = ({
  left,
  right,
  width = 920,
  height = 420,
}) => {
  return (
    <div
      style={{
        width,
        height,
        display: 'flex',
        gap: 24,
        boxSizing: 'border-box',
      }}
    >
      {[left, right].map((side, idx) => {
        const isSuccess = side.isCorrect ?? idx === 1;
        const badgeColor = isSuccess ? '#10B981' : '#EF4444';
        const badgeBg = isSuccess ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';
        const icon = isSuccess ? '✓' : '✗';

        return (
          <div
            key={idx}
            style={{
              flex: 1,
              backgroundColor: '#151722',
              borderRadius: 16,
              border: isSuccess
                ? '1px solid rgba(16, 185, 129, 0.25)'
                : '1px solid rgba(255, 255, 255, 0.08)',
              padding: 24,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            {/* Inner Content Demonstration */}
            <div
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {side.content}
            </div>

            {/* Bottom Status Chip */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                paddingTop: 16,
                borderTop: '1px solid rgba(255, 255, 255, 0.06)',
              }}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  backgroundColor: badgeBg,
                  color: badgeColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 11,
                  fontWeight: 800,
                }}
              >
                {icon}
              </div>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: isSuccess ? '#FFFFFF' : 'rgba(255, 255, 255, 0.65)',
                }}
              >
                {side.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
