import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  icon?: IconName;
  busy?: boolean;
  children?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", icon, busy, className, children, type = "button", ...rest },
  ref,
) {
  const cls = ["btn", `btn--${variant}`, size === "sm" ? "btn--sm" : "", busy ? "is-busy" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <button ref={ref} type={type} className={cls} aria-busy={busy || undefined} {...rest}>
      {busy ? <span className="spinner spinner--inline" aria-hidden="true" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children ? <span className="btn__label">{children}</span> : null}
    </button>
  );
});

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: IconName;
  label: string;
  pressed?: boolean;
  variant?: "tool" | "plain";
}

/** Square icon-only button with an accessible name and a tooltip. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon, label, pressed, variant = "plain", className, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`icon-btn icon-btn--${variant}${className ? ` ${className}` : ""}`}
      aria-label={label}
      aria-pressed={pressed}
      data-tooltip={label}
      {...rest}
    >
      <Icon name={icon} size={20} />
    </button>
  );
});
