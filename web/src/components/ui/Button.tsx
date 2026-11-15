import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" };

export function Button({ variant = "primary", className = "", ...props }: Props) {
  const styles =
    variant === "primary"
      ? "bg-accent text-accent-ink"
      : variant === "danger"
        ? "bg-danger text-bg"
        : "bg-transparent text-ink border border-line";
  return (
    <button
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}

export function IconButton({ label, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button aria-label={label} className={`inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-line ${className}`} {...props} />;
}
