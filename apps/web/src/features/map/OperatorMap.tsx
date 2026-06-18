import type { Feature, Point } from "geojson";
import maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import Map, { Layer, Source, type LayerProps, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import type { Operator, OpportunityHeatmapCell, Signal } from "../../lib/api";
import {
  BC_BBOX,
  heatmapToHexbinFeatureCollection,
  operatorsToFeatureCollection,
  signalsToFeatureCollection
} from "../../lib/geo";
import { MAGMA, mapStyle as luminousMapStyle, surfaces, text } from "../../lib/theme";

export type MapLayers = {
  operators: boolean;
  signals: boolean;
  people: boolean;
  opportunity: boolean;
};

type Props = {
  operators: Operator[];
  heatmapCells: OpportunityHeatmapCell[];
  signals?: Signal[];
  selectedOperatorId: string | null;
  selectedSignalId?: string | null;
  layers?: MapLayers;
  chrome?: boolean;
  onSelectOperator: (operatorId: string) => void;
  onSelectSignal?: (signalId: string) => void;
};

const emptyLayers: MapLayers = {
  operators: true,
  signals: true,
  people: false,
  opportunity: true
};

const darkStyle: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": luminousMapStyle.land }
    }
  ]
} as const;

const clusterLayer: LayerProps = {
  id: "operator-clusters",
  type: "circle",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": luminousMapStyle.pin,
    "circle-opacity": 0.78,
    "circle-radius": ["step", ["get", "point_count"], 15, 25, 21, 80, 29],
    "circle-stroke-color": surfaces.bg,
    "circle-stroke-width": 2
  }
};

const clusterCountLayer: LayerProps = {
  id: "operator-cluster-count",
  type: "symbol",
  filter: ["has", "point_count"],
  layout: {
    "text-field": ["get", "point_count_abbreviated"],
    "text-font": ["Open Sans Bold"],
    "text-size": 11
  },
  paint: {
    "text-color": surfaces.bg
  }
};

const pointLayer: LayerProps = {
  id: "operator-points",
  type: "circle",
  filter: ["!", ["has", "point_count"]],
  paint: {
    "circle-color": [
      "case",
      ["in", ["downcase", ["get", "status"]], ["literal", ["new", "planned", "permit"]]],
      surfaces.bg,
      luminousMapStyle.pin
    ],
    "circle-radius": [
      "case",
      ["in", ["downcase", ["get", "status"]], ["literal", ["new", "planned", "permit"]]],
      4.2,
      luminousMapStyle.pinRadius
    ],
    "circle-opacity": 0.96,
    "circle-stroke-width": [
      "case",
      ["in", ["downcase", ["get", "status"]], ["literal", ["new", "planned", "permit"]]],
      1.8,
      0
    ],
    "circle-stroke-color": luminousMapStyle.pin
  }
};

const selectedLayer: LayerProps = {
  id: "operator-selected",
  type: "circle",
  filter: ["==", ["get", "id"], ""],
  paint: {
    "circle-radius": 14,
    "circle-color": "rgba(255,255,255,0)",
    "circle-stroke-color": luminousMapStyle.selectRing,
    "circle-stroke-width": 1.5
  }
};

const heatmapFillLayer: LayerProps = {
  id: "whitespace-hex-fills",
  type: "fill",
  paint: {
    "fill-color": [
      "interpolate",
      ["linear"],
      ["get", "score"],
      0,
      MAGMA[0],
      0.25,
      MAGMA[1],
      0.45,
      MAGMA[2],
      0.65,
      MAGMA[3],
      0.82,
      MAGMA[4],
      1,
      MAGMA[5]
    ],
    "fill-opacity": ["interpolate", ["linear"], ["get", "score"], 0, 0.16, 1, 0.9]
  }
};

const heatmapLineLayer: LayerProps = {
  id: "whitespace-hex-lines",
  type: "line",
  paint: {
    "line-color": [
      "interpolate",
      ["linear"],
      ["get", "score"],
      0,
      MAGMA[1],
      0.6,
      MAGMA[3],
      1,
      MAGMA[5]
    ],
    "line-opacity": luminousMapStyle.hexStrokeOpacity,
    "line-width": 0.7
  }
};

const signalLayer: LayerProps = {
  id: "signal-points",
  type: "circle",
  paint: {
    "circle-color": ["get", "color"],
    "circle-radius": 4.8,
    "circle-opacity": 0.92,
    "circle-stroke-color": surfaces.bg,
    "circle-stroke-width": 1.2
  }
};

const selectedSignalLayer: LayerProps = {
  id: "signal-selected",
  type: "circle",
  filter: ["==", ["get", "id"], ""],
  paint: {
    "circle-radius": 12,
    "circle-color": "rgba(255,255,255,0)",
    "circle-stroke-color": ["get", "color"],
    "circle-stroke-width": 1.6
  }
};

export function OperatorMap({
  operators,
  heatmapCells,
  signals = [],
  selectedOperatorId,
  selectedSignalId = null,
  layers = emptyLayers,
  chrome = true,
  onSelectOperator,
  onSelectSignal
}: Props) {
  const mapRef = useRef<MapRef | null>(null);
  const [hoveredOperatorId, setHoveredOperatorId] = useState<string | null>(null);
  const operatorData = useMemo(() => operatorsToFeatureCollection(operators), [operators]);
  const heatmapData = useMemo(() => heatmapToHexbinFeatureCollection(heatmapCells), [heatmapCells]);
  const signalData = useMemo(() => signalsToFeatureCollection(signals), [signals]);
  const inspectedOperator =
    operators.find((item) => item.id === (selectedOperatorId ?? hoveredOperatorId)) ?? null;
  const selectedOperatorLayer = useMemo(
    () =>
      ({
        ...selectedLayer,
        filter: ["==", ["get", "id"], selectedOperatorId ?? ""]
      }) as unknown as LayerProps,
    [selectedOperatorId]
  );
  const selectedSignal = signals.find((signal) => signal.id === selectedSignalId) ?? null;
  const selectedSignalCircleLayer = useMemo(
    () =>
      ({
        ...selectedSignalLayer,
        filter: ["==", ["get", "id"], selectedSignalId ?? ""]
      }) as unknown as LayerProps,
    [selectedSignalId]
  );

  useEffect(() => {
    if (!selectedSignal || selectedSignal.lat === null || selectedSignal.lng === null) {
      return;
    }
    mapRef.current?.flyTo({ center: [selectedSignal.lng, selectedSignal.lat], zoom: 13.4, duration: 650 });
  }, [selectedSignal]);

  useEffect(() => {
    if (!selectedOperatorId || selectedSignalId) {
      return;
    }
    const operator = operators.find((item) => item.id === selectedOperatorId);
    if (!operator) {
      return;
    }
    mapRef.current?.flyTo({ center: [operator.lng, operator.lat], zoom: 13, duration: 650 });
  }, [operators, selectedOperatorId, selectedSignalId]);

  function handleClick(event: MapLayerMouseEvent) {
    const signalFeature = event.features?.find((item) => item.layer.id === "signal-points") as
      | Feature<Point, { id?: string; related_operator_id?: string | null }>
      | undefined;
    if (signalFeature?.properties?.id) {
      onSelectSignal?.(signalFeature.properties.id);
      if (signalFeature.properties.related_operator_id) {
        onSelectOperator(signalFeature.properties.related_operator_id);
      }
      return;
    }

    const feature = event.features?.find((item) => item.layer.id === "operator-points") as
      | Feature<Point, { id?: string }>
      | undefined;
    if (feature?.properties?.id) {
      onSelectOperator(feature.properties.id);
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

  const interactiveLayerIds = [
    layers.signals ? "signal-points" : null,
    layers.operators ? "operator-points" : null,
    layers.operators ? "operator-clusters" : null
  ].filter(Boolean) as string[];

  return (
    <section className={`wr-map-stage mapStage${chrome ? "" : " is-compact"}`} aria-label="Operator map">
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
        interactiveLayerIds={interactiveLayerIds}
        onClick={handleClick}
        onMouseMove={(event) => {
          const feature = event.features?.find((item) => item.layer.id === "operator-points");
          setHoveredOperatorId(String(feature?.properties?.id ?? "") || null);
        }}
        onMouseLeave={() => setHoveredOperatorId(null)}
        attributionControl={false}
      >
        {layers.opportunity ? (
          <Source id="whitespace" type="geojson" data={heatmapData}>
            <Layer {...heatmapFillLayer} />
            <Layer {...heatmapLineLayer} />
          </Source>
        ) : null}
        {layers.signals ? (
          <Source id="signals" type="geojson" data={signalData}>
            <Layer {...signalLayer} />
            <Layer {...selectedSignalCircleLayer} />
          </Source>
        ) : null}
        {layers.operators ? (
          <Source id="operators" type="geojson" data={operatorData} cluster clusterRadius={48} clusterMaxZoom={13}>
            <Layer {...clusterLayer} />
            <Layer {...clusterCountLayer} />
            <Layer {...pointLayer} />
            <Layer {...selectedOperatorLayer} />
          </Source>
        ) : null}
      </Map>
      <div className="wr-map-grain" aria-hidden />
      {chrome ? (
        <>
          <div className="wr-map-legend">
            <span>SIGNAL DENSITY / H3 HEXBIN</span>
            <div>
              <i />
              <b>low to high</b>
            </div>
            <p>
              <span className="wr-pin-key" /> operator
              <span className="wr-pin-key is-new" /> new
            </p>
          </div>
          <div className="wr-zoom-control" aria-label="Map zoom controls">
            <button type="button" onClick={() => mapRef.current?.zoomIn()} aria-label="Zoom in">
              +
            </button>
            <button type="button" onClick={() => mapRef.current?.zoomOut()} aria-label="Zoom out">
              -
            </button>
          </div>
        </>
      ) : null}
      {inspectedOperator && !selectedOperatorId ? (
        <div className="wr-map-hover" aria-live="polite">
          <strong>{inspectedOperator.name}</strong>
          <span>{inspectedOperator.neighborhood ?? inspectedOperator.municipality ?? "Metro Vancouver"}</span>
        </div>
      ) : null}
      {chrome ? (
        <div className="wr-map-label" aria-hidden>
          <span>METRO VANCOUVER</span>
          <b style={{ color: text.muted }}>LIVE MAPLIBRE</b>
        </div>
      ) : null}
    </section>
  );
}
