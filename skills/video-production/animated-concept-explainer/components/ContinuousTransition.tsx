import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

export interface ContinuousTransitionProps {
  children: React.ReactNode;
  transitionFrames?: number;
  isFirstScene?: boolean;
}

export const ContinuousTransition: React.FC<ContinuousTransitionProps> = ({
  children,
  transitionFrames = 16,
  isFirstScene = false,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Entrance spring: enters from right (80 -> 0) and scales up (0.96 -> 1.0)
  // The first scene of the video opens rock-solid with zero entrance lag.
  const enterSpring = isFirstScene
    ? 1
    : spring({
        frame,
        fps,
        config: { damping: 16, stiffness: 120, mass: 0.8 },
      });
  const enterX = interpolate(enterSpring, [0, 1], [80, 0]);
  const enterScale = interpolate(enterSpring, [0, 1], [0.96, 1.0]);
  const enterOpacity = interpolate(enterSpring, [0, 1], [0.85, 1.0]);

  // Exit drift: during last transitionFrames, moves left (0 -> -80) and scales down (1.0 -> 0.95)
  const exitProgress = interpolate(
    frame,
    [durationInFrames - transitionFrames, durationInFrames],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );
  const exitX = interpolate(exitProgress, [0, 1], [0, -80]);
  const exitScale = interpolate(exitProgress, [0, 1], [1.0, 0.95]);
  const exitOpacity = interpolate(exitProgress, [0, 1], [1.0, 0.6]);

  const isExiting = frame >= durationInFrames - transitionFrames;
  const currentX = isExiting ? exitX : enterX;
  const currentScale = isExiting ? exitScale : enterScale;
  const currentOpacity = isExiting ? exitOpacity : enterOpacity;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transform: `translateX(${currentX}px) scale(${currentScale})`,
        opacity: currentOpacity,
        transformOrigin: 'center center',
      }}
    >
      {children}
    </div>
  );
};
