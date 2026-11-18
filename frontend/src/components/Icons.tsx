type P = { size?: number; className?: string };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  "aria-hidden": true,
  focusable: false,
});

export const SearchIcon = ({ size = 20, className }: P) => (
  <svg {...base(size)} strokeWidth={2.2} strokeLinecap="round" className={className}>
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-4-4" />
  </svg>
);

export const CameraIcon = ({ size = 22, className }: P) => (
  <svg {...base(size)} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
    <circle cx="12" cy="13" r="3.5" />
  </svg>
);

export const HomeIcon = ({ size = 22, className }: P) => (
  <svg {...base(size)} strokeWidth={2} strokeLinejoin="round" className={className}>
    <path d="M4 11l8-7 8 7v9h-5v-6h-6v6H4z" />
  </svg>
);

export const HangerIcon = ({ size = 22, className }: P) => (
  <svg {...base(size)} strokeWidth={1.8} strokeLinecap="round" className={className}>
    <path d="M12 6a2 2 0 1 1 2 2c-1 0-2 1-2 2v1" />
    <path d="M12 11l-9 6h18z" />
  </svg>
);

export const HeartIcon = ({ size = 22, className, filled = false }: P & { filled?: boolean }) => (
  <svg {...base(size)} strokeWidth={1.8} strokeLinejoin="round" className={className} fill={filled ? "currentColor" : "none"}>
    <path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z" />
  </svg>
);

export const UserIcon = ({ size = 22, className }: P) => (
  <svg {...base(size)} strokeWidth={1.8} className={className}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6" />
  </svg>
);

export const BackIcon = ({ size = 22, className }: P) => (
  <svg {...base(size)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M15 5l-7 7 7 7" />
  </svg>
);

export const PlusIcon = ({ size = 18, className }: P) => (
  <svg {...base(size)} strokeWidth={2.4} strokeLinecap="round" className={className}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const TrashIcon = ({ size = 20, className }: P) => (
  <svg {...base(size)} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />
  </svg>
);

export const ExternalIcon = ({ size = 18, className }: P) => (
  <svg {...base(size)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6" />
  </svg>
);

export const ShirtIcon = ({ size = 48, className }: P) => (
  <svg width={size} height={size} viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden className={className}>
    <path d="M22 10l-12 8 5 10 5-3v29h24V25l5 3 5-10-12-8c-2 4-6 6-10 6s-8-2-10-6z" />
  </svg>
);
