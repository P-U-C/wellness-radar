import type { FeatureCollection, Point } from "geojson";
import type { Operator } from "./api";

export const BC_BBOX = {
  minLng: -123.3,
  minLat: 49.0,
  maxLng: -122.5,
  maxLat: 49.4
};

export function isInBcBounds(lat: number | null, lng: number | null): boolean {
  if (lat === null || lng === null) {
    return false;
  }
  return (
    lat >= BC_BBOX.minLat &&
    lat <= BC_BBOX.maxLat &&
    lng >= BC_BBOX.minLng &&
    lng <= BC_BBOX.maxLng
  );
}

export function operatorsToFeatureCollection(
  operators: Operator[]
): FeatureCollection<Point, { id: string; name: string; category: string; status: string }> {
  return {
    type: "FeatureCollection",
    features: operators
      .filter((operator) => isInBcBounds(operator.lat, operator.lng))
      .map((operator) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [operator.lng, operator.lat] },
        properties: {
          id: operator.id,
          name: operator.name,
          category: operator.categories[0] ?? "allied_health",
          status: operator.status
        }
      }))
  };
}
