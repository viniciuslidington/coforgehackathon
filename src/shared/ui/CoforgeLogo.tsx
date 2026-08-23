'use client';

interface CoforgeIconProps {
  size?: number;
  className?: string;
  theme?: 'dark' | 'light';
}

export function CoforgeIcon({ size = 28, className, theme = 'dark' }: CoforgeIconProps) {
  const rightColor = theme === 'dark' ? '#FFFFFF' : '#0B2341';
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Left half - Coral Orange */}
      <path d="M 50 0 A 50 50 0 0 0 50 100 L 50 74 A 24 24 0 0 1 50 26 Z" fill="#F15A38" />
      {/* Right half */}
      <path d="M 50 0 A 50 50 0 0 1 50 100 L 50 74 A 24 24 0 0 0 50 26 Z" fill={rightColor} />
    </svg>
  );
}

export function CoforgeLogo({ height = 24, className, theme = 'dark' }: { height?: number; className?: string; theme?: 'dark' | 'light' }) {
  const navyOrWhite = theme === 'dark' ? '#FFFFFF' : '#0B2341';
  // Aspect ratio is roughly 360x100
  const width = Math.round(height * 3.6);

  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 360 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* C */}
      <path
        d="M 55 25 A 36 36 0 0 0 18 55 A 36 36 0 0 0 55 85 A 34 34 0 0 0 85 70 L 71 58 A 18 18 0 0 1 55 68 A 18 18 0 0 1 36 55 A 18 18 0 0 1 55 42 A 18 18 0 0 1 71 52 L 85 40 A 34 34 0 0 0 55 25 Z"
        fill="#F15A38"
      />

      {/* o (split circle) */}
      <g transform="translate(100, 30)">
        <path d="M 27 0 A 27 27 0 0 0 27 54 L 27 40 A 13 13 0 0 1 27 14 Z" fill="#F15A38" />
        <path d="M 27 0 A 27 27 0 0 1 27 54 L 27 40 A 13 13 0 0 0 27 14 Z" fill={navyOrWhite} />
      </g>

      {/* f */}
      <path
        d="M 166 22 A 14 14 0 0 1 180 34 L 180 42 L 192 42 L 192 54 L 180 54 L 180 84 L 166 84 L 166 54 L 158 54 L 158 42 L 166 42 L 166 34 A 3 3 0 0 0 163 31 L 157 31 L 157 22 Z"
        fill={navyOrWhite}
      />

      {/* o */}
      <path
        d="M 220 30 A 27 27 0 1 0 220 84 A 27 27 0 1 0 220 30 Z M 220 44 A 13 13 0 1 1 220 70 A 13 13 0 1 1 220 44 Z"
        fill={navyOrWhite}
      />

      {/* r */}
      <path
        d="M 258 42 L 271 42 L 271 50 A 14 14 0 0 1 286 42 L 286 56 A 14 14 0 0 0 271 62 L 271 84 L 258 84 Z"
        fill={navyOrWhite}
      />

      {/* g */}
      <path
        d="M 312 30 A 27 27 0 0 0 286 57 A 27 27 0 0 0 312 84 L 312 90 A 14 14 0 0 1 298 104 L 287 104 L 287 116 L 298 116 A 26 26 0 0 0 326 90 L 326 32 L 312 32 Z M 312 44 L 312 70 A 13 13 0 1 1 312 44 Z"
        fill={navyOrWhite}
      />

      {/* e */}
      <path
        d="M 358 52 A 27 27 0 0 0 331 30 A 27 27 0 0 0 331 84 A 27 27 0 0 0 358 72 L 347 62 A 15 15 0 0 1 331 70 A 14 14 0 0 1 317 56 L 358 56 Z M 317 48 A 14 14 0 0 1 331 43 A 14 14 0 0 1 345 48 Z"
        fill={navyOrWhite}
      />
    </svg>
  );
}
