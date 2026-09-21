import type { ReactNode } from "react";
import type { QcStatus } from "../../data/types";
import "./StatusBadge.css";

const CONFIG: Record<QcStatus, { label: string; className: string; icon: ReactNode }> = {
  pass: {
    label: "QC ok",
    className: "status-badge--good",
    icon: (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M1.5 5.2 L4 7.7 L8.5 2.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  warning: {
    label: "QC warning",
    className: "status-badge--warning",
    icon: (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M5 1.2 L9.3 8.6 L0.7 8.6 Z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
        <line x1="5" y1="4" x2="5" y2="6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="5" cy="7.4" r="0.6" fill="currentColor" />
      </svg>
    ),
  },
  fail: {
    label: "QC failed",
    className: "status-badge--critical",
    icon: (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <line x1="2" y1="2" x2="8" y2="8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <line x1="8" y1="2" x2="2" y2="8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
};

export function StatusBadge({ status }: { status: QcStatus }) {
  const cfg = CONFIG[status];
  return (
    <span className={`status-badge ${cfg.className}`}>
      {cfg.icon}
      {cfg.label}
    </span>
  );
}
