// 선 아이콘: 이모지 대신 사용 (OS 마다 모양·색이 달라지지 않고, 글자색과 테마를 따름)
// - 24 격자, 선 굵기 1.8, 둥근 끝

const PATHS = {
  dashboard: 'M4 13h6V4H4zM14 20h6v-9h-6zM4 20h6v-3H4zM14 7h6V4h-6z',
  inbox: 'M4 13h4l1.5 3h5L16 13h4M5.5 5h13L20 13v6H4v-6z',
  review: 'M12 8v4l2.5 1.5M3.5 12a8.5 8.5 0 1 0 2.5-6M3 4v4h4',
  rules: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4',
  report: 'M4 20V10M10 20V4M16 20v-7M21 20H3',
  settings:
    'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 13.5l1.6 1.2-2 3.4-1.9-.7a7 7 0 0 1-1.9 1.1L15 20.5h-4l-.3-2a7 7 0 0 1-1.9-1.1l-1.9.7-2-3.4 1.6-1.2a7 7 0 0 1 0-2.2L4.9 10.1l2-3.4 1.9.7a7 7 0 0 1 1.9-1.1l.3-2h4l.3 2a7 7 0 0 1 1.9 1.1l1.9-.7 2 3.4-1.6 1.2a7 7 0 0 1 0 2.2z',
  bell: 'M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2.2 2.2 0 0 0 4 0',
  bellOff: 'M6 16V11a6 6 0 0 1 9.5-4.9M18 11v5l1.5 2H8M10 20.5a2.2 2.2 0 0 0 4 0M4 4l16 16',
  moon: 'M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4',
  calendar: 'M4 6.5h16V20H4zM4 10.5h16M8.5 3.5v4M15.5 3.5v4',
  chevronLeft: 'M14.5 6 8.5 12l6 6',
  chevronRight: 'M9.5 6l6 6-6 6',
} as const;

export type IconName = keyof typeof PATHS;

export default function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
