import React from 'react';

export interface SkeletonLineProps {
  width?: number | string;
  height?: number;
  highlight?: boolean;
  accentColor?: string;
  style?: React.CSSProperties;
}

export const SkeletonLine: React.FC<SkeletonLineProps> = ({
  width = '100%',
  height = 10,
  highlight = false,
  accentColor = '#8B5CF6',
  style,
}) => {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 9999,
        backgroundColor: highlight ? `${accentColor}40` : 'rgba(255, 255, 255, 0.12)',
        boxShadow: highlight ? `0 0 12px ${accentColor}30` : 'none',
        flexShrink: 0,
        ...style,
      }}
    />
  );
};

export interface SkeletonBlockProps {
  width?: number | string;
  height?: number | string;
  borderRadius?: number;
  highlight?: boolean;
  accentColor?: string;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

export const SkeletonBlock: React.FC<SkeletonBlockProps> = ({
  width = '100%',
  height = 120,
  borderRadius = 12,
  highlight = false,
  accentColor = '#8B5CF6',
  children,
  style,
}) => {
  return (
    <div
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: highlight ? '#1F1B2E' : '#181A24',
        border: highlight
          ? `1px solid ${accentColor}50`
          : '1px solid rgba(255, 255, 255, 0.06)',
        display: 'flex',
        flexDirection: 'column',
        padding: 16,
        boxSizing: 'border-box',
        position: 'relative',
        ...style,
      }}
    >
      {children}
    </div>
  );
};
