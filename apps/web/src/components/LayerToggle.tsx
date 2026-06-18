import type { EntityType } from "../lib/theme";
import { entity } from "../lib/theme";

type Props = {
  type: EntityType;
  label: string;
  count: number | string;
  on: boolean;
  onToggle: () => void;
};

export function LayerToggle({ type, label, count, on, onToggle }: Props) {
  return (
    <button
      className={`wr-layer-toggle wr-layer-${type}${on ? " is-on" : ""}`}
      type="button"
      aria-pressed={on}
      onClick={onToggle}
    >
      <span className="wr-layer-dot" style={{ background: entity[type] }} />
      <span className="wr-layer-label">{label}</span>
      <span className="wr-layer-count">{count}</span>
    </button>
  );
}
