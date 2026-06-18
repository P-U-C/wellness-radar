export const surfaces = {
  bg: "#080D18",
  panel: "#0F1622",
  raised: "#16202E",
  line: "#212D3D",
  line2: "#2B3A4D"
} as const;

export const text = {
  primary: "#EAF0F7",
  dim: "#C2CEDB",
  body: "#A6B0BC",
  muted: "#8595A8",
  faint: "#5A6A7E"
} as const;

export const entity = {
  operator: "#38BDF8",
  signal: "#F5A524",
  people: "#A78BFA",
  opportunity: "#34D399",
  danger: "#F87171"
} as const;

export type EntityType = keyof typeof entity;

export const trustTier: Record<string, string> = {
  official: "#38BDF8",
  reputable_press: "#34D399",
  commercial_api: "#A78BFA",
  community: "#F5A524",
  informal: "#8595A8",
  ai_inferred: "#5A6A7E"
};

export const MAGMA = ["#1b0c33", "#451077", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"] as const;

export function magma(t: number): string {
  const stops = MAGMA;
  const normalized = Math.max(0, Math.min(1, t));
  const segment = normalized * (stops.length - 1);
  const index = Math.floor(segment);
  const fraction = segment - index;
  if (index >= stops.length - 1) {
    return stops[stops.length - 1];
  }
  const a = hexToRgb(stops[index]);
  const b = hexToRgb(stops[index + 1]);
  return rgbToHex([
    a[0] + (b[0] - a[0]) * fraction,
    a[1] + (b[1] - a[1]) * fraction,
    a[2] + (b[2] - a[2]) * fraction
  ]);
}

function hexToRgb(value: string): [number, number, number] {
  const hex = value.replace("#", "");
  return [
    parseInt(hex.slice(0, 2), 16),
    parseInt(hex.slice(2, 4), 16),
    parseInt(hex.slice(4, 6), 16)
  ];
}

function rgbToHex(values: number[]): string {
  return `#${values
    .map((value) => Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, "0"))
    .join("")}`;
}

export const radius = { xs: 4, sm: 6, md: 8, lg: 11, xl: 13, pill: 999 } as const;
export const space = { 1: 6, 2: 10, 3: 14, 4: 18, 5: 22, 6: 28 } as const;

export const font = {
  ui: "'Space Grotesk', ui-sans-serif, system-ui, sans-serif",
  mono: "'Space Mono', ui-monospace, 'SF Mono', monospace"
} as const;

export const mapStyle = {
  land: "#0d1320",
  water: "#070b14",
  graticule: "#1a2436",
  label: "#8595A8",
  labelHalo: "#070b14",
  pin: "#38BDF8",
  pinNew: "#38BDF8",
  pinGlowOpacity: 0.14,
  pinRadius: 3,
  pinRadiusSelected: 3.6,
  selectRing: "#38BDF8",
  hexFillRamp: MAGMA,
  hexFillOpacity: (value: number) => 0.16 + 0.74 * value,
  hexStrokeOpacity: 0.25,
  hexApproxResolution: 8
} as const;

export const signalTypeColor: Record<string, string> = {
  new_operator: entity.signal,
  new_operator_opening: entity.signal,
  opening: entity.signal,
  press: entity.operator,
  news: entity.operator,
  whitespace: entity.opportunity,
  opportunity: entity.opportunity,
  recall: entity.danger,
  regulatory: entity.danger,
  osm_observation: text.muted
};

export function colorForTrustTier(tier: string): string {
  return trustTier[tier] ?? text.muted;
}

export function colorForSignalType(type: string): string {
  return signalTypeColor[type] ?? entity.signal;
}
