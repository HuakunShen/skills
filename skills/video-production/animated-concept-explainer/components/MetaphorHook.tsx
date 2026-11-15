import React from 'react';

export interface MetaphorHookProps {
  x: number;
  y: number; // hook tip position
  lineLength?: number;
  hookColor?: string;
}

export const MetaphorHook: React.FC<MetaphorHookProps> = ({
  x,
  y,
  lineLength = 220,
  hookColor = '#CBD5E1',
}) => {
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y - lineLength,
        pointerEvents: 'none',
        zIndex: 100,
      }}
    >
      {/* Hanging Monofilament Line */}
      <div
        style={{
          width: 1,
          height: lineLength,
          backgroundColor: 'rgba(255, 255, 255, 0.45)',
          margin: '0 auto',
        }}
      />

      {/* SVG Fishing Hook */}
      <svg
        width="28"
        height="36"
        viewBox="0 0 24 32"
        fill="none"
        style={{
          marginLeft: -14,
          filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.5))',
        }}
      >
        <path
          d="M12 0V18C12 23 7 26 3 22C-1 18 2 12 7 14"
          stroke={hookColor}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* Barb */}
        <path d="M5 16L7 14L6 19" stroke={hookColor} strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  );
};
