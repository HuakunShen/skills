import React from 'react';

export interface MetricSliderProps {
  label: string;
  value: number; // 0 to 100
  min?: number;
  max?: number;
  height?: number;
  width?: number;
  orientation?: 'vertical' | 'horizontal';
  accent?: string;
  showTicks?: boolean;
}

export const MetricSlider: React.FC<MetricSliderProps> = ({
  label = 'taste',
  value = 50,
  min = 0,
  max = 100,
  height = 260,
  width = 54,
  orientation = 'vertical',
  accent = '#8B5CF6',
  showTicks = true,
}) => {
  const clampedVal = Math.min(Math.max(value, min), max);
  const percentage = ((clampedVal - min) / (max - min)) * 100;

  if (orientation === 'vertical') {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 12,
          userSelect: 'none',
        }}
      >
        {/* Track Container */}
        <div
          style={{
            width,
            height,
            backgroundColor: '#161822',
            borderRadius: 24,
            border: '1px solid rgba(255, 255, 255, 0.08)',
            position: 'relative',
            display: 'flex',
            justifyContent: 'center',
            boxShadow: '0 12px 28px rgba(0, 0, 0, 0.45)',
            overflow: 'hidden',
          }}
        >
          {/* Tick marks */}
          {showTicks && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                padding: '24px 0',
                opacity: 0.25,
              }}
            >
              {[0, 1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  style={{
                    width: 14,
                    height: 2,
                    backgroundColor: '#FFFFFF',
                    borderRadius: 1,
                  }}
                />
              ))}
            </div>
          )}

          {/* Active Fill Gradient */}
          <div
            style={{
              position: 'absolute',
              bottom: 0,
              width: '100%',
              height: `${percentage}%`,
              background: `linear-gradient(to top, ${accent}30, ${accent}80)`,
              borderTop: `2px solid ${accent}`,
              transition: 'height 0.1s ease-out',
            }}
          />

          {/* Glowing Slider Indicator / Needle */}
          <div
            style={{
              position: 'absolute',
              bottom: `calc(${percentage}% - 6px)`,
              left: 4,
              right: 4,
              height: 12,
              backgroundColor: '#FFFFFF',
              borderRadius: 6,
              boxShadow: `0 0 16px ${accent}, 0 2px 4px rgba(0,0,0,0.5)`,
            }}
          />
        </div>

        {/* Label */}
        <span
          style={{
            fontSize: 13,
            color: 'rgba(255, 255, 255, 0.70)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            fontWeight: 600,
            letterSpacing: '0.04em',
            textTransform: 'lowercase',
          }}
        >
          {label}
        </span>
      </div>
    );
  }

  // Horizontal variant
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: 280 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 13, color: accent, fontWeight: 700 }}>{Math.round(percentage)}%</span>
      </div>
      <div
        style={{
          height: 16,
          backgroundColor: '#161822',
          borderRadius: 8,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${percentage}%`,
            background: `linear-gradient(to right, ${accent}40, ${accent})`,
            borderRadius: 8,
          }}
        />
      </div>
    </div>
  );
};
