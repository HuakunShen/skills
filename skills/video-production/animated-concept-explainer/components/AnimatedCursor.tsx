import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { CursorType, Point } from './types';

export interface Waypoint {
  frame: number;
  x: number;
  y: number;
  click?: boolean;
}

export interface AnimatedCursorProps {
  start?: Point;
  target?: Point;
  startFrame?: number;
  endFrame?: number;
  clickFrame?: number;
  waypoints?: Waypoint[];
  type?: CursorType;
  accentColor?: string;
  showTrail?: boolean;
}

export const AnimatedCursor: React.FC<AnimatedCursorProps> = ({
  start = { x: 100, y: 100 },
  target = { x: 100, y: 100 },
  startFrame = 0,
  endFrame = 30,
  clickFrame,
  waypoints,
  type = 'arrow',
  accentColor = '#8B5CF6',
  showTrail = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  let currentX = start.x;
  let currentY = start.y;
  let effectiveClickFrame: number | undefined = clickFrame;

  if (waypoints && waypoints.length >= 2) {
    // Find active segment
    if (frame <= waypoints[0].frame) {
      currentX = waypoints[0].x;
      currentY = waypoints[0].y;
    } else if (frame >= waypoints[waypoints.length - 1].frame) {
      const last = waypoints[waypoints.length - 1];
      currentX = last.x;
      currentY = last.y;
    } else {
      let idx = 0;
      for (let i = 0; i < waypoints.length - 1; i++) {
        if (frame >= waypoints[i].frame && frame < waypoints[i + 1].frame) {
          idx = i;
          break;
        }
      }
      const w0 = waypoints[idx];
      const w1 = waypoints[idx + 1];
      const progress = interpolate(frame, [w0.frame, w1.frame], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
      const dx = w1.x - w0.x;
      const dy = w1.y - w0.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const curvature = dist > 10 ? Math.min(dist * 0.22, 100) : 0;
      const ctrl: Point = dist > 10
        ? {
            x: (w0.x + w1.x) / 2 - (dy / dist) * curvature,
            y: (w0.y + w1.y) / 2 + (dx / dist) * curvature,
          }
        : { x: w0.x, y: w0.y };

      currentX =
        (1 - progress) ** 2 * w0.x + 2 * (1 - progress) * progress * ctrl.x + progress ** 2 * w1.x;
      currentY =
        (1 - progress) ** 2 * w0.y + 2 * (1 - progress) * progress * ctrl.y + progress ** 2 * w1.y;
    }

    // Determine if any waypoint clicked recently
    for (const w of waypoints) {
      if (w.click && frame >= w.frame && frame <= w.frame + 35) {
        effectiveClickFrame = w.frame;
      }
    }
  } else {
    // Standard 2-point interpolation
    const progress = interpolate(frame, [startFrame, endFrame], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

    const dx = target.x - start.x;
    const dy = target.y - start.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const curvature = Math.min(dist * 0.25, 120);

    const ctrl: Point = {
      x: (start.x + target.x) / 2 - (dy / (dist || 1)) * curvature,
      y: (start.y + target.y) / 2 + (dx / (dist || 1)) * curvature,
    };

    currentX =
      (1 - progress) ** 2 * start.x + 2 * (1 - progress) * progress * ctrl.x + progress ** 2 * target.x;
    currentY =
      (1 - progress) ** 2 * start.y + 2 * (1 - progress) * progress * ctrl.y + progress ** 2 * target.y;
  }

  // Click Animation: Spring depression & ripple ring
  const hasClicked = effectiveClickFrame !== undefined && frame >= effectiveClickFrame;
  const clickAge = hasClicked ? frame - effectiveClickFrame! : 0;

  const clickScale = hasClicked
    ? spring({
        frame: clickAge,
        fps,
        config: { damping: 15, stiffness: 240, mass: 0.5 },
      })
    : 1;

  // Compress to 0.88 on click, then bounce back
  const cursorScale = hasClicked && clickAge < 20 ? interpolate(clickScale, [0, 1], [0.88, 1]) : 1;

  // Expanding ripple ring
  const rippleRadius = hasClicked && clickAge < 25
    ? interpolate(clickAge, [0, 25], [0, 48], { extrapolateRight: 'clamp' })
    : 0;
  const rippleOpacity = hasClicked && clickAge < 25
    ? interpolate(clickAge, [0, 25], [0.65, 0], { extrapolateRight: 'clamp' })
    : 0;

  // Switch to pointing hand if near target or clicked
  const effectiveType = hasClicked && clickAge < 30 ? 'hand' : type;

  return (
    <div
      style={{
        position: 'absolute',
        left: currentX,
        top: currentY,
        pointerEvents: 'none',
        zIndex: 9999,
        transform: `translate(-2px, -2px) scale(${cursorScale})`,
        transformOrigin: '0 0',
      }}
    >
      {/* Click Ripple Effect */}
      {hasClicked && clickAge < 25 && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width: rippleRadius * 2,
            height: rippleRadius * 2,
            borderRadius: '50%',
            border: `2px solid ${accentColor}`,
            opacity: rippleOpacity,
            transform: 'translate(-50%, -50%)',
          }}
        />
      )}

      {/* SVG Cursor Icons */}
      {effectiveType === 'hand' ? (
        <svg
          width="26"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          style={{ filter: 'drop-shadow(0 3px 6px rgba(0,0,0,0.65))' }}
        >
          <path
            d="M9 11V4.5a1.5 1.5 0 0 1 3 0V10M12 10.5V6a1.5 1.5 0 0 1 3 0v4.5M15 11V7.5a1.5 1.5 0 0 1 3 0v5a5.5 5.5 0 0 1-5.5 5.5h-1a5.5 5.5 0 0 1-4.8-2.8L5 13.5a1.5 1.5 0 0 1 2.3-1.8L9 13"
            stroke="#FFFFFF"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="#111216"
          />
        </svg>
      ) : (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          style={{ filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.75))' }}
        >
          <path
            d="M3 3L10.07 20.97L13.58 13.58L20.97 10.07L3 3Z"
            fill="#FFFFFF"
            stroke="#111216"
            strokeWidth="2"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </div>
  );
};
