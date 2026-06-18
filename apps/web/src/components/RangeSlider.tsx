import type { CSSProperties } from "react";

type Props = {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  color?: "magma" | "ok";
  onChange: (value: number) => void;
};

export function RangeSlider({ label, value, min = 0, max = 1, step = 0.01, color = "magma", onChange }: Props) {
  const percent = ((value - min) / (max - min)) * 100;

  return (
    <label
      className={`wr-range wr-range-${color}`}
      style={{ "--wr-range-value": `${Math.max(0, Math.min(100, percent))}%` } as CSSProperties}
    >
      <span>
        {label}
        <strong>{value.toFixed(2)}</strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
