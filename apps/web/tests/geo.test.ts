import { describe, expect, it } from "vitest";
import {
  heatmapToHexbinFeatureCollection,
  isInBcBounds,
  operatorsToFeatureCollection,
  signalsToFeatureCollection
} from "../src/lib/geo";
import type { Operator, OpportunityHeatmapCell, Signal } from "../src/lib/api";

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

const baseSignal: Signal = {
  id: "sig_test",
  type: "press",
  severity: "info",
  title: "Signal",
  summary: null,
  why_it_matters: null,
  source_name: "Test source",
  source_url: null,
  trust_tier: "official",
  occurred_at: "2026-01-01T00:00:00Z",
  lat: 49.2827,
  lng: -123.1207,
  related_operator_id: "op_test",
  confidence_score: 0.9,
  source_refs: []
};

const baseCell: OpportunityHeatmapCell = {
  id: "cell_test",
  category: "recovery_contrast_therapy",
  geo_code: "geo_test",
  geo_name: "Mount Pleasant",
  geo_level: "CSD",
  lat: 49.263,
  lng: -123.102,
  supply_count: 2,
  operator_ids: ["op_test"],
  population: 41000,
  business_count: null,
  opportunity_score: 0.8,
  component_breakdown: {},
  calculation_method: "test",
  source_refs: [],
  confidence_score: 0.9,
  trace_payload: {},
  generated_at: "2026-01-01T00:00:00Z"
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

  it("filters non-BC signals before map rendering", () => {
    const collection = signalsToFeatureCollection([
      baseSignal,
      { ...baseSignal, id: "sig_wa", lat: 45.6387, lng: -122.6615 }
    ]);

    expect(collection.features).toHaveLength(1);
    expect(collection.features[0].properties.id).toBe("sig_test");
  });

  it("bins whitespace cells into client-side hex polygons", () => {
    const collection = heatmapToHexbinFeatureCollection([
      baseCell,
      { ...baseCell, id: "cell_near", geo_name: "Riley Park", opportunity_score: 0.6, supply_count: 1 }
    ]);

    expect(collection.features).toHaveLength(1);
    expect(collection.features[0].geometry.type).toBe("Polygon");
    expect(collection.features[0].geometry.coordinates[0]).toHaveLength(7);
    expect(collection.features[0].properties.cell_count).toBe(2);
    expect(collection.features[0].properties.supply_count).toBe(3);
    expect(collection.features[0].properties.score).toBeCloseTo(0.7);
  });

  it("filters non-BC whitespace cells before hexbin rendering", () => {
    const collection = heatmapToHexbinFeatureCollection([
      baseCell,
      { ...baseCell, id: "cell_wa", lat: 45.6387, lng: -122.6615 }
    ]);

    expect(collection.features).toHaveLength(1);
    expect(collection.features[0].properties.geo_name).toBe("Mount Pleasant");
  });
});
