import { describe, expect, it } from "vitest";
import { MAGMA, colorForTrustTier, magma } from "../src/lib/theme";

describe("luminous theme", () => {
  it("keeps magma endpoints stable", () => {
    expect(magma(0)).toBe(MAGMA[0]);
    expect(magma(1)).toBe(MAGMA[MAGMA.length - 1]);
  });

  it("clamps magma input", () => {
    expect(magma(-1)).toBe(MAGMA[0]);
    expect(magma(2)).toBe(MAGMA[MAGMA.length - 1]);
  });

  it("maps canonical trust tiers", () => {
    expect(colorForTrustTier("official")).toBe("#38BDF8");
    expect(colorForTrustTier("reputable_press")).toBe("#34D399");
  });
});
