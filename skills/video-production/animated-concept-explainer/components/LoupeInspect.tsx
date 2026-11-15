import React from 'react';

export interface LoupeInspectProps {
  x: number;
  y: number;
  radius?: number;
  zoomScale?: number;
  accentColor?: string;
  active?: boolean;
  children?: React.ReactNode;
}

export const LoupeInspect: React.FC<LoupeInspectProps> = ({
  x,
  y,
  radius = 64,
  zoomScale = 1.35,
  accentColor = '#8B5CF6',
  active = true,
  children,
}) => {
  if (!active) return <>{children}</>;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Normal Base Layer */}
      {children}

      {/* Floating Loupe Lens */}
      <div
        style={{
          position: 'absolute',
          left: x - radius,
          top: y - radius,
          width: radius * 2,
          height: radius * 2,
          borderRadius: '50%',
          border: `2px solid ${accentColor}`,
          boxShadow: `0 0 24px ${accentColor}40, inset 0 0 16px rgba(0,0,0,0.5)`,
          overflow: 'hidden',
          pointerEvents: 'none',
          zIndex: 1000,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: -(x * zoomScale - radius),
            top: -(y * zoomScale - radius),
            transform: `scale(${zoomScale})`,
            transformOrigin: '0 0',
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};
