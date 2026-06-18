import type { EntityType } from "../lib/theme";
import { entity } from "../lib/theme";

type Props = {
  type: EntityType;
  label?: string;
};

export function EntityBadge({ type, label = type }: Props) {
  return (
    <span className={`wr-entity-badge wr-entity-${type}`}>
      <span className="wr-entity-dot" style={{ background: entity[type] }} />
      {label}
    </span>
  );
}
