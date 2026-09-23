import type { ReactNode } from "react";

type Tone = "advisory" | "stop" | "plain";

/** Inline notice. Always rendered in flow, never inside a tooltip. */
export function Notice({
  tone = "plain",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "stop" ? "alert" : "note"}>
      {title ? <strong>{title}</strong> : null}
      {children}
    </div>
  );
}
