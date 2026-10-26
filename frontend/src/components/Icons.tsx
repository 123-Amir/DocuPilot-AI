import type { ReactNode } from "react";

type IconProps = { className?: string };

function Svg({
  className,
  children,
  viewBox = "0 0 24 24",
}: IconProps & { children: ReactNode; viewBox?: string }) {
  return (
    <svg
      className={className ?? "h-5 w-5"}
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const DashboardIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </Svg>
);

export const UploadIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M12 16V4" />
    <path d="m7 9 5-5 5 5" />
    <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </Svg>
);

export const ShieldIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M12 3 4.5 6v5.2c0 4.4 3.1 8.3 7.5 9.8 4.4-1.5 7.5-5.4 7.5-9.8V6Z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);

export const AlertIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M10.3 4.2 2.8 17.3A1.9 1.9 0 0 0 4.5 20h15a1.9 1.9 0 0 0 1.7-2.7L13.7 4.2a1.9 1.9 0 0 0-3.4 0Z" />
    <path d="M12 9v4" />
    <path d="M12 16.5h.01" />
  </Svg>
);

export const ArrowLeftIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M19 12H5" />
    <path d="m11 18-6-6 6-6" />
  </Svg>
);

export const ArrowRightIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M5 12h14" />
    <path d="m13 6 6 6-6 6" />
  </Svg>
);

export const FileIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 17h4" />
  </Svg>
);

export const ChatIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M20 15a2 2 0 0 1-2 2H8l-4 3V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2Z" />
    <path d="M8 9h8M8 13h5" />
  </Svg>
);

export const SparkIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
    <path d="m6.3 6.3 2 2M15.7 15.7l2 2M17.7 6.3l-2 2M8.3 15.7l-2 2" />
    <circle cx="12" cy="12" r="2.6" />
  </Svg>
);

export const ExternalIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M14 4h6v6" />
    <path d="m20 4-8 8" />
    <path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" />
  </Svg>
);

export const CheckIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m5 12 4 4L19 6" />
  </Svg>
);

export const CloseIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Svg>
);

export const ClockIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Svg>
);

export const LockIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="4" y="10" width="16" height="10" rx="2" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </Svg>
);

export const ScanIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M3 8V5a2 2 0 0 1 2-2h3" />
    <path d="M16 3h3a2 2 0 0 1 2 2v3" />
    <path d="M21 16v3a2 2 0 0 1-2 2h-3" />
    <path d="M8 21H5a2 2 0 0 1-2-2v-3" />
    <path d="M7 12h10" />
  </Svg>
);

export const RefreshIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M20 11a8 8 0 1 0-2.3 6.7" />
    <path d="M20 4v7h-7" />
  </Svg>
);

export const SearchIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </Svg>
);
