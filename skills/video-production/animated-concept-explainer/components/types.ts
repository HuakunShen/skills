export interface Point {
  x: number;
  y: number;
}

export type CursorType = 'arrow' | 'hand' | 'text';

export interface MomentClip {
  id: string;
  title: string;
  durationSeconds: number;
  active?: boolean;
  thumbnailIcon?: string;
  statusBadge?: string;
}

export interface ComparativeCard {
  title: string;
  badge: {
    label: string;
    type: 'success' | 'error' | 'warning' | 'neutral';
  };
  content: React.ReactNode;
}
