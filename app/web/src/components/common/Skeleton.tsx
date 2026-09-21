import type { CSSProperties } from "react";
import "./Skeleton.css";

export function Skeleton({
  width,
  height,
  style,
}: {
  width?: string | number;
  height?: string | number;
  style?: CSSProperties;
}) {
  return (
    <div
      className="skeleton"
      style={{ width, height, ...style }}
      aria-hidden="true"
    />
  );
}
