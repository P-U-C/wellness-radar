import type { Feature, Point } from "geojson";
import maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import Map, {
  Layer,
  Popup,
  Source,
  type LayerProps,
  type MapLayerMouseEvent,
  type MapRef
} from "react-map-gl/maplibre";
import type { Operator, OpportunityHeatmapCell, Signal } from "../../lib/api";
import {
  BC_BBOX,
  heatmapToHexbinFeatureCollection,
  isInBcBounds,
  operatorsToFeatureCollection,
  signalsToFeatureCollection
} from "../../lib/geo";
import { MAGMA, surfaces, text } from "../../lib/theme";

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
  activeBundleLabel?: string | null;
  fitKey?: string | null;
  onSelectOperator: (operatorId: string) => void;
  onClearOperator?: () => void;
  onSelectSignal?: (signalId: string) => void;
};

const emptyLayers: MapLayers = {
  operators: true,
  signals: true,
  people: false,
  opportunity: true
};

const STREET_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

const clusterLayer: LayerProps = {
  id: "operator-clusters",
  type: "circle",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": ["step", ["get", "point_count"], "#0ea5e9", 25, "#0284c7", 80, "#0369a1"],
    "circle-opacity": 0.9,
    "circle-radius": ["step", ["get", "point_count"], 17, 25, 23, 80, 31],
    "circle-stroke-color": "#ffffff",
    "circle-stroke-width": 2.4
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
      "#f97316",
      "#0ea5e9"
    ],
    "circle-radius": [
      "case",
      ["in", ["downcase", ["get", "status"]], ["literal", ["new", "planned", "permit"]]],
      6.4,
      7.4
    ],
    "circle-opacity": 0.96,
    "circle-stroke-width": 2.2,
    "circle-stroke-color": "#ffffff"
  }
};

const selectedLayer: LayerProps = {
  id: "operator-selected",
  type: "circle",
  filter: ["==", ["get", "id"], ""],
  paint: {
    "circle-radius": 16,
    "circle-color": "rgba(255,255,255,0)",
    "circle-stroke-color": "#f59e0b",
    "circle-stroke-width": 2.4
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
    "line-opacity": 0.72,
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
  activeBundleLabel = null,
  fitKey = null,
  onSelectOperator,
  onClearOperator,
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
  const selectedOperator = operators.find((item) => item.id === selectedOperatorId) ?? null;
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
    if (!fitKey || selectedOperatorId) {
      return;
    }
    const bounds = new maplibregl.LngLatBounds();
    let pointCount = 0;
    for (const operator of operators) {
      if (!isInBcBounds(operator.lat, operator.lng)) {
        continue;
      }
      bounds.extend([operator.lng, operator.lat]);
      pointCount += 1;
    }
    if (pointCount === 0) {
      return;
    }
    if (pointCount === 1) {
      const center = bounds.getCenter();
      mapRef.current?.flyTo({ center, zoom: 13.5, duration: 650 });
      return;
    }
    mapRef.current?.fitBounds(bounds, {
      padding: { top: 64, right: 64, bottom: 64, left: 64 },
      maxZoom: 13.8,
      duration: 700
    });
  }, [fitKey, operators, selectedOperatorId]);

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
        mapStyle={STREET_STYLE_URL}
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
        attributionControl={{ compact: true }}
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
        {selectedOperator && isInBcBounds(selectedOperator.lat, selectedOperator.lng) ? (
          <Popup
            className="wr-operator-popup"
            longitude={selectedOperator.lng}
            latitude={selectedOperator.lat}
            anchor="bottom"
            offset={18}
            closeOnClick={false}
            onClose={onClearOperator}
          >
            <OperatorPopup operator={selectedOperator} bundleLabel={activeBundleLabel} />
          </Popup>
        ) : null}
      </Map>
      {chrome ? (
        <>
          <div className="wr-map-legend">
            <span>PLACES</span>
            <p>
              <span className="wr-pin-key" /> operator
              <span className="wr-pin-key is-new" /> planned
              <span className="wr-cluster-key" /> cluster
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
          <b style={{ color: text.muted }}>OPENFREEMAP / OSM</b>
        </div>
      ) : null}
    </section>
  );
}

function OperatorPopup({ operator, bundleLabel }: { operator: Operator; bundleLabel: string | null }) {
  const contacts = operatorPopupContacts(operator);
  return (
    <div className="wr-popup-card">
      <div className="wr-popup-head">
        <strong>{operator.name}</strong>
        <span>{sentenceLabel(operator.status)}</span>
      </div>
      <div className="wr-popup-meta">
        <span>{bundleLabel ?? sentenceLabel(operator.categories[0] ?? "wellness")}</span>
        <span>{operator.neighborhood ?? operator.municipality ?? "Metro Vancouver"}</span>
      </div>
      {operator.address ? <p>{operator.address}</p> : null}
      {contacts.length > 0 ? (
        <div className="wr-popup-contacts">
          {contacts.map((contact) => (
            <a key={`${contact.type}:${contact.value}`} href={contact.href} target={contact.external ? "_blank" : undefined} rel={contact.external ? "noreferrer" : undefined}>
              {contact.label}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function operatorPopupContacts(operator: Operator): Array<{
  type: string;
  label: string;
  value: string;
  href: string;
  external: boolean;
}> {
  const rows = new globalThis.Map<
    string,
    { type: string; label: string; value: string; href: string; external: boolean }
  >();

  function add(type: string | undefined, value: string | null | undefined, platform?: string | null) {
    if (!type || !value) {
      return;
    }
    const normalizedType = type.toLowerCase();
    const href = contactHref(normalizedType, value);
    if (!href) {
      return;
    }
    const key = `${normalizedType}:${value}`;
    rows.set(key, {
      type: normalizedType,
      label: platform ? sentenceLabel(platform) : contactLabel(normalizedType),
      value,
      href,
      external: normalizedType === "website" || normalizedType === "social"
    });
  }

  for (const contact of operator.contacts ?? []) {
    add(contact.contact_type ?? contact.type, contact.value, contact.platform);
  }
  add("phone", operator.phone);
  add("website", operator.website);
  for (const [platform, value] of Object.entries(operator.social_links ?? {})) {
    add("social", String(value), platform);
  }

  return Array.from(rows.values()).slice(0, 5);
}

function contactHref(type: string, value: string): string | null {
  if (type === "phone") {
    const compact = value.replace(/[^\d+]/g, "");
    return compact ? `tel:${compact}` : null;
  }
  if (type === "email") {
    return `mailto:${value}`;
  }
  if (type === "website" || type === "social") {
    return /^https?:\/\//i.test(value) ? value : `https://${value}`;
  }
  return null;
}

function contactLabel(type: string): string {
  switch (type) {
    case "phone":
      return "Call";
    case "email":
      return "Email";
    case "website":
      return "Website";
    case "social":
      return "Social";
    default:
      return sentenceLabel(type);
  }
}

function sentenceLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bIv\b/g, "IV");
}
