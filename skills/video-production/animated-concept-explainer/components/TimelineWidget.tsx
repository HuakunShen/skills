import React from 'react';
import { MomentClip } from './types';

export interface TimelineWidgetProps {
  moments: MomentClip[];
  currentTime?: number;
  maxTime?: number;
  targetRange?: [number, number]; // e.g. [10, 16] seconds
  bracketLabel?: string;
  accentColor?: string;
}

export const TimelineWidget: React.FC<TimelineWidgetProps> = ({
  moments = [],
  currentTime = 7.5,
  maxTime = 20,
  targetRange = [10, 16],
  bracketLabel = 'One action',
  accentColor = '#F97316',
}) => {
  const [minTarget, maxTarget] = targetRange;
  const progressRatio = (currentTime / maxTime) * 100;

  return (
    <div
      style={{
        width: 1040,
        backgroundColor: '#15161F',
        borderRadius: 16,
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 24px 50px rgba(0, 0, 0, 0.65)',
        padding: '16px 24px 28px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        userSelect: 'none',
        boxSizing: 'border-box',
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          paddingBottom: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Pixel Mascot or Avatar */}
          <div
            style={{
              width: 24,
              height: 24,
              backgroundColor: '#F97316',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 14,
            }}
          >
            👾
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#FFFFFF' }}>
            {moments.length} moments
          </span>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ opacity: 0.6, fontSize: 16 }}>✂️</span>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              backgroundColor: `${accentColor}30`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: accentColor,
              fontSize: 12,
            }}
          >
            ▶
          </div>
          {/* Zoom Slider */}
          <div
            style={{
              width: 80,
              height: 4,
              backgroundColor: 'rgba(255,255,255,0.15)',
              borderRadius: 2,
              position: 'relative',
            }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                backgroundColor: '#FFFFFF',
                position: 'absolute',
                top: -3,
                left: 35,
              }}
            />
          </div>
        </div>
      </div>

      {/* Timeline Ruler & Moment Cards Track */}
      <div style={{ position: 'relative', marginTop: 8 }}>
        {/* Time ruler ticks */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 11,
            color: 'rgba(255, 255, 255, 0.35)',
            fontFamily: 'monospace',
            marginBottom: 8,
            paddingLeft: 4,
            paddingRight: 4,
          }}
        >
          <span>0s</span>
          <span>5s</span>
          <span style={{ color: '#F97316', fontWeight: 700 }}>10s</span>
          <span style={{ color: '#F97316', fontWeight: 700 }}>16s</span>
          <span>20s</span>
        </div>

        {/* Target Range Guidelines (10s and 16s markers) */}
        <div
          style={{
            position: 'absolute',
            top: 24,
            bottom: 0,
            left: `${(minTarget / maxTime) * 100}%`,
            width: 1,
            backgroundColor: '#F97316',
            boxShadow: '0 0 8px #F97316',
            zIndex: 10,
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: 24,
            bottom: 0,
            left: `${(maxTarget / maxTime) * 100}%`,
            width: 1,
            backgroundColor: '#F97316',
            boxShadow: '0 0 8px #F97316',
            zIndex: 10,
          }}
        />

        {/* Moment Cards Filmstrip */}
        <div
          style={{
            display: 'flex',
            gap: 12,
            position: 'relative',
            backgroundColor: '#101118',
            borderRadius: 12,
            padding: 8,
            border: '1px solid rgba(255, 255, 255, 0.05)',
          }}
        >
          {moments.map((m, idx) => (
            <div
              key={m.id || idx}
              style={{
                flex: m.durationSeconds,
                height: 72,
                backgroundColor: m.active ? '#242138' : '#1A1C28',
                borderRadius: 8,
                border: m.active
                  ? '1px solid #8B5CF6'
                  : '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                gap: 6,
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 6,
                  borderRadius: 3,
                  backgroundColor: m.active ? '#8B5CF6' : 'rgba(255,255,255,0.2)',
                }}
              />
              <span
                style={{
                  fontSize: 10,
                  color: 'rgba(255, 255, 255, 0.60)',
                  fontWeight: 500,
                }}
              >
                {m.title}
              </span>
            </div>
          ))}

          {/* Active Playhead Scrubber */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: `${progressRatio}%`,
              width: 2,
              backgroundColor: '#FFFFFF',
              zIndex: 20,
              boxShadow: '0 0 10px #FFFFFF',
            }}
          >
            <div
              style={{
                position: 'absolute',
                top: -6,
                left: -5,
                width: 12,
                height: 12,
                borderRadius: 2,
                backgroundColor: '#F97316',
              }}
            />
          </div>
        </div>
      </div>

      {/* Bracket Annotation */}
      {bracketLabel && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            marginTop: 4,
          }}
        >
          <div
            style={{
              width: '85%',
              height: 8,
              borderBottom: '2px solid rgba(255, 255, 255, 0.25)',
              borderLeft: '2px solid rgba(255, 255, 255, 0.25)',
              borderRight: '2px solid rgba(255, 255, 255, 0.25)',
            }}
          />
          <span
            style={{
              marginTop: 6,
              fontSize: 13,
              color: 'rgba(255, 255, 255, 0.85)',
              fontWeight: 600,
            }}
          >
            {bracketLabel}
          </span>
        </div>
      )}
    </div>
  );
};
