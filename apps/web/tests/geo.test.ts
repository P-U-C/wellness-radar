import { describe, expect, it } from "vitest";
import { isInBcBounds, operatorsToFeatureCollection } from "../src/lib/geo";
import type { Operator } from "../src/lib/api";

const baseOperator: Operator = {
  id: "op_test",
  name: "Test Wellness",
  categories: ["allied_health"],
  status: "open",
  address: "Vancouver, BC",
  municipality: "Vancouver",
  neighborhood: null,
  lat: 49.2827,
  lng: -123.1207,
  confidence_score: 0.9,
  source_refs: []
};

describe("geo guard", () => {
  it("accepts Metro Vancouver coordinates", () => {
    expect(isInBcBounds(49.2827, -123.1207)).toBe(true);
  });

  it("rejects Vancouver Washington coordinates", () => {
    expect(isInBcBounds(45.6387, -122.6615)).toBe(false);
  });

  it("filters non-BC operators before map rendering", () => {
    const collection = operatorsToFeatureCollection([
      baseOperator,
      { ...baseOperator, id: "op_wa", lat: 45.6387, lng: -122.6615 }
    ]);

    expect(collection.features).toHaveLength(1);
    expect(collection.features[0].properties.id).toBe("op_test");
  });
});
