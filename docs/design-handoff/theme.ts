// ============================================================
// Wellness Radar — "Luminous" theme (TypeScript)
// For apps/web (React + TS + MapLibre GL).
// Mirrors tokens.css. Import where you need values in JS/TSX.
// ============================================================

export const surfaces = {
  bg: "#080D18",
  panel: "#0F1622",
  raised: "#16202E",
  line: "#212D3D",
  line2: "#2B3A4D",
} as const;

export const text = {
  primary: "#EAF0F7",
  dim: "#C2CEDB",
  body: "#A6B0BC",
  muted: "#8595A8",
  faint: "#5A6A7E",
} as const;

// Object-type accents — key by canonical entity type
export const entity = {
  operator: "#38BDF8",
  signal: "#F5A524",
  people: "#A78BFA",
  opportunity: "#34D399",
  danger: "#F87171",
} as const;

// source_refs[].trust_tier  ->  color  (canonical.py TRUST_TIERS)
export const trustTier: Record<string, string> = {
  official: "#38BDF8",
  reputable_press: "#34D399",
  commercial_api: "#A78BFA",
  community: "#F5A524",
  informal: "#8595A8",
  ai_inferred: "#5A6A7E",
};

// Magma ramp — colorblind-safe. Use for confidence + density + opportunity.
export const MAGMA = ["#1b0c33", "#451077", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"] as const;

/** Map a 0..1 score to a magma hex (linear interpolation between stops). */
export function magma(t: number): string {
  const stops = MAGMA;
  t = Math.max(0, Math.min(1, t));
  const seg = t * (stops.length - 1);
  const i = Math.floor(seg);
  const f = seg - i;
  if (i >= stops.length - 1) return stops[stops.length - 1];
  const a = hex2rgb(stops[i]);
  const b = hex2rgb(stops[i + 1]);
  return rgb2hex([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]);
}
function hex2rgb(x: string) { const h = x.replace("#", ""); return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)]; }
function rgb2hex(a: number[]) { return "#" + a.map(v => Math.max(0,Math.min(255,Math.round(v))).toString(16).padStart(2,"0")).join(""); }

export const radius = { xs: 4, sm: 6, md: 8, lg: 11, xl: 13, pill: 999 } as const;
export const space  = { 1: 6, 2: 10, 3: 14, 4: 18, 5: 22, 6: 28 } as const;

export const font = {
  ui: "'Space Grotesk', ui-sans-serif, system-ui, sans-serif",
  mono: "'Space Mono', ui-monospace, 'SF Mono', monospace",
} as const;

// ============================================================
// MapLibre GL style tokens
// The prototype draws a stylized SVG basemap; in production keep the
// existing built-in MapLibre style but recolor these layers to match.
// ============================================================
export const mapStyle = {
  land: "#0d1320",      // background / land fill
  water: "#070b14",     // water bodies (Burrard Inlet, False Creek, Fraser)
  graticule: "#1a2436", // arterials / boundaries, ~1px, 55% opacity
  label: "#8595A8",     // place labels
  labelHalo: "#070b14",

  // Operator pins (circle layer) — keep clustering as-is
  pin: "#38BDF8",
  pinNew: "#38BDF8",         // status "new"/"planned": hollow ring (stroke only)
  pinGlowOpacity: 0.14,      // soft halo behind each pin
  pinRadius: 3,
  pinRadiusSelected: 3.6,

  // Selected operator: 14px ring (stroke 1.5) + crosshair ticks in accent.
  selectRing: "#38BDF8",

  // H3 hexbin heat layer (Signals density / Opportunity score)
  // Production: aggregate records into H3 cells, fill by score with magma().
  hexFillRamp: MAGMA,
  hexFillOpacity: (v: number) => 0.16 + 0.74 * v, // v = normalized score 0..1
  hexStrokeOpacity: 0.25,
  hexApproxResolution: 8, // r≈27px on the prototype's 1000x600 viewBox proxy
} as const;
