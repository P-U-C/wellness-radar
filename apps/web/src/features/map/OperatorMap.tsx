import type { Feature, Point } from "geojson";
import maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";
import Map, { Layer, Source, type LayerProps, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import type { Operator, OpportunityHeatmapCell } from "../../lib/api";
import { BC_BBOX, heatmapToFeatureCollection, operatorsToFeatureCollection } from "../../lib/geo";

type Props = {
  operators: Operator[];
  heatmapCells: OpportunityHeatmapCell[];
  selectedOperatorId: string | null;
  onSelectOperator: (operatorId: string) => void;
};

const darkStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#101214" }
    }
  ]
} as const;

const clusterLayer: LayerProps = {
  id: "operator-clusters",
  type: "circle",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": "#2bd4a7",
    "circle-opacity": 0.82,
    "circle-radius": ["step", ["get", "point_count"], 18, 25, 24, 80, 32],
    "circle-stroke-color": "#f5f0e8",
    "circle-stroke-width": 1
  }
};

const clusterCountLayer: LayerProps = {
  id: "operator-cluster-count",
  type: "symbol",
  filter: ["has", "point_count"],
  layout: {
    "text-field": ["get", "point_count_abbreviated"],
    "text-size": 12
  },
  paint: {
    "text-color": "#101214"
  }
};

const pointLayer: LayerProps = {
  id: "operator-points",
  type: "circle",
  filter: ["!", ["has", "point_count"]],
  paint: {
    "circle-color": [
      "match",
      ["get", "category"],
      "recovery_contrast_therapy",
      "#ff6b6b",
      "spa_thermal",
      "#f2c94c",
      "fitness_movement",
      "#7dd3fc",
      "community_social_wellness",
      "#c084fc",
      "#2bd4a7"
    ],
    "circle-radius": 8,
    "circle-opacity": 0.9,
    "circle-stroke-width": 2,
    "circle-stroke-color": [
      "case",
      ["==", ["get", "status"], "closed"],
      "#5d646b",
      "#f5f0e8"
    ]
  }
};

const selectedLayer: LayerProps = {
  id: "operator-selected",
  type: "circle",
  filter: ["==", ["get", "id"], ""],
  paint: {
    "circle-radius": 15,
    "circle-color": "rgba(255, 255, 255, 0)",
    "circle-stroke-color": "#ffffff",
    "circle-stroke-width": 3
  }
};

const heatmapLayer: LayerProps = {
  id: "whitespace-cells",
  type: "circle",
  paint: {
    "circle-color": [
      "interpolate",
      ["linear"],
      ["get", "score"],
      0.2,
      "#27415f",
      0.45,
      "#2bd4a7",
      0.7,
      "#f2c94c",
      0.9,
      "#ff6b6b"
    ],
    "circle-radius": ["interpolate", ["linear"], ["get", "score"], 0.2, 18, 0.9, 46],
    "circle-opacity": 0.34,
    "circle-stroke-color": "#f5f0e8",
    "circle-stroke-opacity": 0.3,
    "circle-stroke-width": 1
  }
};

export function OperatorMap({ operators, heatmapCells, selectedOperatorId, onSelectOperator }: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const data = useMemo(() => operatorsToFeatureCollection(operators), [operators]);
  const heatmapData = useMemo(() => heatmapToFeatureCollection(heatmapCells), [heatmapCells]);
  const selected = useMemo(
    () =>
      ({
        ...selectedLayer,
        filter: ["==", ["get", "id"], selectedOperatorId ?? ""]
      }) as unknown as LayerProps,
    [selectedOperatorId]
  );

  useEffect(() => {
    if (!selectedOperatorId) {
      return;
    }
    const operator = operators.find((item) => item.id === selectedOperatorId);
    if (!operator) {
      return;
    }
    mapRef.current?.flyTo({ center: [operator.lng, operator.lat], zoom: 13, duration: 650 });
  }, [operators, selectedOperatorId]);

  function handleClick(event: MapLayerMouseEvent) {
    const feature = event.features?.find((item) => item.layer.id === "operator-points") as
      | Feature<Point, { id?: string }>
      | undefined;
    if (feature?.properties?.id) {
      const operator = operators.find((item) => item.id === feature.properties?.id);
      if (operator) {
        onSelectOperator(operator.id);
      }
      return;
    }

    const cluster = event.features?.find((item) => item.layer.id === "operator-clusters");
    if (cluster) {
      mapRef.current?.easeTo({
        center: [event.lngLat.lng, event.lngLat.lat],
        zoom: Math.min(event.target.getZoom() + 1.5, 16)
      });
    }
  }

  return (
    <section className="mapStage" aria-label="Operator map">
      <Map
        ref={mapRef}
        mapLib={maplibregl}
        mapStyle={darkStyle}
        initialViewState={{ longitude: -123.1207, latitude: 49.255, zoom: 10.3 }}
        maxBounds={[
          [BC_BBOX.minLng, BC_BBOX.minLat],
          [BC_BBOX.maxLng, BC_BBOX.maxLat]
        ]}
        minZoom={9}
        maxZoom={17}
        interactiveLayerIds={["operator-points", "operator-clusters"]}
        onClick={handleClick}
        attributionControl={false}
      >
        <Source id="whitespace" type="geojson" data={heatmapData}>
          <Layer {...heatmapLayer} />
        </Source>
        <Source id="operators" type="geojson" data={data} cluster clusterRadius={48} clusterMaxZoom={13}>
          <Layer {...clusterLayer} />
          <Layer {...clusterCountLayer} />
          <Layer {...pointLayer} />
          <Layer {...selected} />
        </Source>
      </Map>
      <div className="mapLegend">
        <span><i className="legendRecovery" />Recovery</span>
        <span><i className="legendSpa" />Spa</span>
        <span><i className="legendFitness" />Fitness</span>
        <span><i className="legendAllied" />Allied</span>
        <span><i className="legendWhitespace" />White-space</span>
      </div>
    </section>
  );
}
