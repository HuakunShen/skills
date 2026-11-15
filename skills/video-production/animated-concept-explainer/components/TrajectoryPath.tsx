import React from 'react';
import { Point } from './types';

export interface TrajectoryPathProps {
  start: Point;
  control: Point;
  end: Point;
  strokeColor?: string;
  strokeWidth?: number;
  dashed?: boolean;
  arrow?: boolean;
}

export const TrajectoryPath: React.FC<TrajectoryPathProps> = ({
  start,
  control,
  end,
  strokeColor = 'rgba(255, 255, 255, 0.40)',
  strokeWidth = 2,
  dashed = true,
  arrow = true,
}) => {
  const pathD = `M ${start.x} ${start.y} Q ${control.x} ${control.y} ${end.x} ${end.y}`;

  // Calculate tangent angle at end point for arrowhead orientation
  const angleRad = Math.atan2(end.y - control.y, end.x - control.x);
  const angleDeg = (angleRad * 180) / Math.PI;

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 50,
      }}
    >
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeDasharray={dashed ? '5,5' : undefined}
      />

      {/* Terminal Arrowhead */}
      {arrow && (
        <g transform={`translate(${end.x}, ${end.y}) rotate(${angleDeg})`}>
          <polygon points="-8,-5 0,0 -8,5" fill={strokeColor} />
        </g>
      )}
    </svg>
  );
};
