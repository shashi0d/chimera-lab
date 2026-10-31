import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** "plain" is the white card; "well" a recessed panel; "glass" the floating chrome. */
  variant?: "plain" | "well" | "glass";
  padding?: "none" | "sm" | "md";
  as?: "div" | "section" | "article";
  children: ReactNode;
}

/** ZD Card: --surface-card, --radius-2xl, --border-card, --shadow-card. */
export function Card({ variant = "plain", padding = "md", as: Tag = "div", className, children, ...rest }: CardProps) {
  return (
    <Tag className={`card card--${variant} card--pad-${padding}${className ? ` ${className}` : ""}`} {...rest}>
      {children}
    </Tag>
  );
}
