// Small hand-drawn icon set: 20px grid, 1.5px strokes, square caps (see DESIGN.md).

const PATHS = {
  plus: "M10 4v12M4 10h12",
  brush: "M16.5 3.5 9 11M9 11l-2.5 0a2.5 2.5 0 0 0-2.5 2.5c0 1.5-.5 2.5-1.5 3h4a3.5 3.5 0 0 0 3.5-3.5L9 11z",
  star: "M10 3l2.1 4.4 4.9.6-3.6 3.4.9 4.8L10 13.9 5.7 16.2l.9-4.8L3 8l4.9-.6z",
  download: "M10 3.5v9M6 8.5l4 4 4-4M3.5 16.5h13",
  chat: "M3.5 4.5h13v9h-7l-4 3v-3h-2z",
  eye: "M2.5 10s3-5.5 7.5-5.5 7.5 5.5 7.5 5.5-3 5.5-7.5 5.5S2.5 10 2.5 10zM10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  globe: "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15zM2.5 10h15M10 2.5c2 2 3 4.5 3 7.5s-1 5.5-3 7.5c-2-2-3-4.5-3-7.5s1-5.5 3-7.5z",
  user: "M10 10a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM3.5 17.5c.8-3 3.4-5 6.5-5s5.7 2 6.5 5",
  image: "M3.5 4.5h13v11h-13zM3.5 13l4-4 3.5 3.5 2-2 3.5 3.5M12.5 7.5h.01",
  fusion: "M7.5 6.5a3.5 3.5 0 1 0 0 7M12.5 6.5a3.5 3.5 0 1 1 0 7M7.5 10h5",
  result: "M4 3.5h12v13H4zM4 13.5h12M7 16.5v-3",
  fit: "M3.5 7.5v-4h4M12.5 3.5h4v4M16.5 12.5v4h-4M7.5 16.5h-4v-4",
  undo: "M7 5 3.5 8.5 7 12M3.5 8.5h8a4.5 4.5 0 0 1 0 9H8",
  redo: "M13 5l3.5 3.5L13 12M16.5 8.5h-8a4.5 4.5 0 0 0 0 9H12",
  map: "M3.5 5.5 8 3.5l4 2 4.5-2v11L12 16.5l-4-2-4.5 2zM8 3.5v11M12 5.5v11",
  sun: "M10 6.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7M10 2.5v1.5M10 16v1.5M2.5 10H4M16 10h1.5M4.7 4.7l1 1M14.3 14.3l1 1M4.7 15.3l1-1M14.3 5.7l1-1",
  moon: "M15.5 12.5A6.5 6.5 0 0 1 7.5 4.5a6.5 6.5 0 1 0 8 8z",
  help: "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15zM7.8 7.8a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.4v.7M10 14.5h.01",
  close: "M5 5l10 10M15 5 5 15",
  check: "M4 10.5l3.5 3.5L16 5.5",
  alert: "M10 3l7.5 13.5h-15zM10 8v4M10 14.5h.01",
  error: "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15zM7 7l6 6M13 7l-6 6",
  info: "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15zM10 9v5M10 6.2h.01",
  left: "M12 4.5 6.5 10l5.5 5.5",
  right: "M8 4.5l5.5 5.5L8 15.5",
  upload: "M10 13V3.5M6 7.5l4-4 4 4M3.5 13v3.5h13V13",
  refresh: "M16 10a6 6 0 1 1-1.8-4.3M16 3.5v3.5h-3.5",
  trash: "M4 5.5h12M8 5.5V3.5h4v2M5.5 5.5l.8 11h7.4l.8-11",
  pencil: "M13.5 3.5l3 3L7 16H4v-3zM11.5 5.5l3 3",
  folder: "M3 5.5h5l1.5 2H17v8.5H3z",
  copy: "M7.5 7.5h9v9h-9zM12.5 7.5v-4h-9v9h4",
  stop: "M5.5 5.5h9v9h-9z",
  offline: "M3 3l14 14M6.5 8.6A5 5 0 0 0 5 12.5h0a3 3 0 0 0 0 6h9M10 5.5a5.5 5.5 0 0 1 5.4 4.4A3.3 3.3 0 0 1 17 15.6",
  minus: "M4 10h12",
  replace: "M4 7.5h10l-3-3M16 12.5H6l3 3",
  leaf: "M4 16c0-7 4-11.5 12-12-0.5 8-5 12-12 12zM4 16l6-6",
  card: "M3.5 4.5h13v11h-13zM6 7.5h3v3H6zM11 8h3.5M11 10.5h3.5M6 13h8.5",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
  /** If set, the icon is announced; otherwise it is decorative. */
  label?: string;
}

export function Icon({ name, size = 20, className, label }: IconProps) {
  return (
    <svg
      className={`icon${className ? ` ${className}` : ""}`}
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      strokeLinejoin="miter"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
