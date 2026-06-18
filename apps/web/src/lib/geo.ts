import type { FeatureCollection, Point, Polygon } from "geojson";
import type { Operator, OpportunityHeatmapCell, Signal } from "./api";
import { colorForSignalType } from "./theme";

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
): FeatureCollection<
  Point,
  {
    id: string;
    name: string;
    category: string;
    status: string;
    source: string;
    freshness: string;
  }
> {
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
          status: operator.status,
          source: operator.source_refs[0]?.source_name ?? "unknown",
          freshness:
            operator.freshness_age_hours === null || operator.freshness_age_hours === undefined
              ? "unknown"
              : `${Math.round(operator.freshness_age_hours)}h`
        }
      }))
  };
}

export function heatmapToFeatureCollection(
  cells: OpportunityHeatmapCell[]
): FeatureCollection<Point, { id: string; geo_name: string; score: number; supply_count: number }> {
  return {
    type: "FeatureCollection",
    features: cells
      .filter((cell) => isInBcBounds(cell.lat, cell.lng))
      .map((cell) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [cell.lng as number, cell.lat as number] },
        properties: {
          id: cell.id,
          geo_name: cell.geo_name,
          score: cell.opportunity_score,
          supply_count: cell.supply_count
        }
      }))
  };
}

export type HexbinProperties = {
  id: string;
  geo_name: string;
  geo_names: string;
  score: number;
  supply_count: number;
  population: number | null;
  cell_count: number;
  confidence_score: number;
};

type HexAccumulator = {
  id: string;
  q: number;
  r: number;
  scoreTotal: number;
  confidenceTotal: number;
  supplyCount: number;
  population: number;
  populationSeen: boolean;
  cells: OpportunityHeatmapCell[];
};

const HEX_CENTER = { lat: 49.2, lng: -122.9 };
const METERS_PER_DEGREE_LAT = 111_320;

export function heatmapToHexbinFeatureCollection(
  cells: OpportunityHeatmapCell[],
  radiusMeters = 2_800
): FeatureCollection<Polygon, HexbinProperties> {
  const bins = new Map<string, HexAccumulator>();

  for (const cell of cells) {
    if (!isInBcBounds(cell.lat, cell.lng)) {
      continue;
    }
    const point = lngLatToMeters(cell.lng as number, cell.lat as number);
    const axial = pixelToAxial(point.x, point.y, radiusMeters);
    const key = `${axial.q}:${axial.r}`;
    const existing =
      bins.get(key) ??
      ({
        id: key,
        q: axial.q,
        r: axial.r,
        scoreTotal: 0,
        confidenceTotal: 0,
        supplyCount: 0,
        population: 0,
        populationSeen: false,
        cells: []
      } satisfies HexAccumulator);

    existing.scoreTotal += cell.opportunity_score;
    existing.confidenceTotal += cell.confidence_score;
    existing.supplyCount += cell.supply_count;
    if (cell.population !== null) {
      existing.population += cell.population;
      existing.populationSeen = true;
    }
    existing.cells.push(cell);
    bins.set(key, existing);
  }

  return {
    type: "FeatureCollection",
    features: Array.from(bins.values()).map((bin) => {
      const center = axialToPixel(bin.q, bin.r, radiusMeters);
      const centerLngLat = metersToLngLat(center.x, center.y);
      const sortedCells = [...bin.cells].sort((a, b) => b.opportunity_score - a.opportunity_score);
      const score = bin.scoreTotal / bin.cells.length;
      const confidence = bin.confidenceTotal / bin.cells.length;
      return {
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [hexagonRing(centerLngLat.lng, centerLngLat.lat, radiusMeters)]
        },
        properties: {
          id: bin.id,
          geo_name: sortedCells[0]?.geo_name ?? "Unknown area",
          geo_names: sortedCells.map((cell) => cell.geo_name).join(", "),
          score,
          supply_count: bin.supplyCount,
          population: bin.populationSeen ? bin.population : null,
          cell_count: bin.cells.length,
          confidence_score: confidence
        }
      };
    })
  };
}

export function signalsToFeatureCollection(
  signals: Signal[]
): FeatureCollection<
  Point,
  {
    id: string;
    type: string;
    title: string;
    color: string;
    related_operator_id: string | null;
  }
> {
  return {
    type: "FeatureCollection",
    features: signals
      .filter((signal) => isInBcBounds(signal.lat, signal.lng))
      .map((signal) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [signal.lng as number, signal.lat as number] },
        properties: {
          id: signal.id,
          type: signal.type,
          title: signal.title,
          color: colorForSignalType(signal.type),
          related_operator_id: signal.related_operator_id
        }
      }))
  };
}

function lngLatToMeters(lng: number, lat: number): { x: number; y: number } {
  const lngScale = Math.cos((HEX_CENTER.lat * Math.PI) / 180) * METERS_PER_DEGREE_LAT;
  return {
    x: (lng - HEX_CENTER.lng) * lngScale,
    y: (lat - HEX_CENTER.lat) * METERS_PER_DEGREE_LAT
  };
}

function metersToLngLat(x: number, y: number): { lng: number; lat: number } {
  const lngScale = Math.cos((HEX_CENTER.lat * Math.PI) / 180) * METERS_PER_DEGREE_LAT;
  return {
    lng: HEX_CENTER.lng + x / lngScale,
    lat: HEX_CENTER.lat + y / METERS_PER_DEGREE_LAT
  };
}

function pixelToAxial(x: number, y: number, size: number): { q: number; r: number } {
  const q = ((Math.sqrt(3) / 3) * x - y / 3) / size;
  const r = ((2 / 3) * y) / size;
  return roundAxial(q, r);
}

function axialToPixel(q: number, r: number, size: number): { x: number; y: number } {
  return {
    x: size * Math.sqrt(3) * (q + r / 2),
    y: size * 1.5 * r
  };
}

function roundAxial(q: number, r: number): { q: number; r: number } {
  let x = q;
  let z = r;
  let y = -x - z;
  let rx = Math.round(x);
  let ry = Math.round(y);
  let rz = Math.round(z);
  const xDiff = Math.abs(rx - x);
  const yDiff = Math.abs(ry - y);
  const zDiff = Math.abs(rz - z);

  if (xDiff > yDiff && xDiff > zDiff) {
    rx = -ry - rz;
  } else if (yDiff > zDiff) {
    ry = -rx - rz;
  } else {
    rz = -rx - ry;
  }

  return { q: rx, r: rz };
}

function hexagonRing(lng: number, lat: number, radiusMeters: number): number[][] {
  const center = lngLatToMeters(lng, lat);
  const ring = Array.from({ length: 6 }, (_, index) => {
    const angle = (Math.PI / 180) * (60 * index - 30);
    const point = metersToLngLat(
      center.x + radiusMeters * Math.cos(angle),
      center.y + radiusMeters * Math.sin(angle)
    );
    return [Number(point.lng.toFixed(6)), Number(point.lat.toFixed(6))];
  });
  return [...ring, ring[0]];
}
