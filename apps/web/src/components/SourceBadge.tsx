import type { SourceLabel } from "../types";

const LABELS: Record<SourceLabel, string> = {
  green: "已核实",
  blue: "OSM",
  gray: "未核实",
};

type SourceBadgeProps = {
  label?: SourceLabel;
};

export function SourceBadge({ label = "blue" }: SourceBadgeProps) {
  return (
    <span className={`source-badge source-badge--${label}`} title={LABELS[label]}>
      {LABELS[label]}
    </span>
  );
}
