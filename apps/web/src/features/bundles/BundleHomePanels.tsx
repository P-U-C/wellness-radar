import { BarChart3, MapPin, UserRound, Users } from "lucide-react";
import type { BundleDetail, BundleGeoConcentration, BundleSummary } from "../../lib/api";
import { formatScore } from "../../lib/format";

type BundleRailProps = {
  bundles: BundleSummary[];
  selectedBundleId: string | null;
  mappedPlaceCount: number;
  omittedPlaceCount: number;
  onSelectBundle: (bundleId: string) => void;
  onClearBundle: () => void;
};

type BundleDetailPanelProps = {
  bundle: BundleSummary | null;
  detail: BundleDetail | null;
  loading: boolean;
  error: string | null;
  mappedPlaceCount: number;
  omittedPlaceCount: number;
};

export function BundleRail({
  bundles,
  selectedBundleId,
  mappedPlaceCount,
  omittedPlaceCount,
  onSelectBundle,
  onClearBundle
}: BundleRailProps) {
  return (
    <aside className="wr-bundle-rail" aria-label="Bundle rankings">
      <div className="wr-bundle-rail-head">
        <div>
          <span>BUNDLE + SCORE</span>
          <h1>Ranked wellness bundles</h1>
        </div>
      </div>

      <button
        className={`wr-bundle-all ${selectedBundleId === null ? "is-active" : ""}`}
        type="button"
        onClick={onClearBundle}
        aria-pressed={selectedBundleId === null}
      >
        <MapPin size={17} />
        <span>
          <strong>All places</strong>
          <b>
            {mappedPlaceCount} mapped
            {omittedPlaceCount > 0 ? ` / ${omittedPlaceCount} missing lat/lng` : ""}
          </b>
        </span>
      </button>

      <div className="wr-bundle-card-list">
        {bundles.map((bundle, index) => {
          const active = bundle.id === selectedBundleId;
          const momentum = numberComponent(bundle.components, "momentum") ?? bundle.score;
          return (
            <button
              key={bundle.id}
              className={`wr-bundle-card ${active ? "is-active" : ""}`}
              type="button"
              onClick={() => onSelectBundle(bundle.id)}
              aria-pressed={active}
            >
              <span className="wr-bundle-rank">{index + 1}</span>
              <span className="wr-bundle-card-main">
                <span className="wr-bundle-card-title">
                  <strong>{bundle.label}</strong>
                  <b>{formatScore(bundle.score)}</b>
                </span>
                <span className="wr-bundle-card-meta">
                  <Users size={13} />
                  {bundle.member_count} places
                  {topGeoLabel(bundle) ? ` / ${topGeoLabel(bundle)}` : ""}
                </span>
                <span className="wr-bundle-score-track" aria-hidden>
                  <i style={{ width: `${Math.max(4, Math.min(100, bundle.score * 100))}%` }} />
                </span>
                <span className="wr-bundle-momentum">
                  momentum <b>{formatPercent(momentum)}</b>
                </span>
              </span>
            </button>
          );
        })}
        {bundles.length === 0 ? <p className="wr-bundle-empty">No bundles returned.</p> : null}
      </div>
    </aside>
  );
}

export function BundleDetailPanel({
  bundle,
  detail,
  loading,
  error,
  mappedPlaceCount,
  omittedPlaceCount
}: BundleDetailPanelProps) {
  if (!bundle) {
    return (
      <aside className="wr-bundle-detail-panel" aria-label="Map coverage">
        <div className="wr-bundle-detail-head">
          <span>WHAT'S AVAILABLE</span>
          <h2>Metro Vancouver places</h2>
          <strong>{mappedPlaceCount}</strong>
        </div>
        <div className="wr-bundle-detail-section">
          <dl className="wr-bundle-facts">
            <div>
              <dt>mapped pins</dt>
              <dd>{mappedPlaceCount}</dd>
            </div>
            <div>
              <dt>omitted without lat/lng</dt>
              <dd>{omittedPlaceCount}</dd>
            </div>
          </dl>
        </div>
      </aside>
    );
  }

  const activeDetail = detail ?? bundle;
  const scoreRows = componentRows(activeDetail.components);
  const geographyRows = topGeographies(activeDetail.geography);
  const topPeople = detail?.top_people ?? [];

  return (
    <aside className="wr-bundle-detail-panel" aria-label="Selected bundle details">
      <div className="wr-bundle-detail-head">
        <span>SELECTED BUNDLE</span>
        <h2>{bundle.label}</h2>
        <strong>{formatScore(bundle.score)}</strong>
      </div>

      <div className="wr-bundle-detail-section">
        <h3>
          <BarChart3 size={15} />
          Score breakdown
        </h3>
        <div className="wr-component-list">
          {scoreRows.map((row) => (
            <div key={row.key}>
              <span>
                {row.label}
                <b>{formatComponentValue(row.value)}</b>
              </span>
              <i aria-hidden>
                <b style={{ width: `${Math.max(3, Math.min(100, normalizedScore(row.value) * 100))}%` }} />
              </i>
            </div>
          ))}
          {scoreRows.length === 0 ? <p>No component rows returned.</p> : null}
        </div>
      </div>

      <div className="wr-bundle-detail-section">
        <h3>
          <MapPin size={15} />
          Geography
        </h3>
        <div className="wr-geo-list">
          {geographyRows.map((geo) => (
            <div key={`${geo.geo_level}:${geo.geo_name}`}>
              <span>{geo.geo_name}</span>
              <b>{geo.member_count} places</b>
            </div>
          ))}
          {geographyRows.length === 0 ? <p>No geography rows returned.</p> : null}
        </div>
      </div>

      <div className="wr-bundle-detail-section">
        <h3>
          <UserRound size={15} />
          Top people
        </h3>
        {loading && topPeople.length === 0 ? <p>Loading people.</p> : null}
        {error ? <p>{error}</p> : null}
        <div className="wr-top-people-list">
          {topPeople.map((person) => (
            <article key={person.id}>
              <div>
                <strong>{person.name}</strong>
                <span>{personRole(person)}</span>
              </div>
              <p>{person.why_appears}</p>
              {person.influence_score !== null ? <b>{formatScore(person.influence_score)}</b> : null}
            </article>
          ))}
          {!loading && !error && topPeople.length === 0 ? <p>No top people returned.</p> : null}
        </div>
      </div>
    </aside>
  );
}

function numberComponent(components: Record<string, unknown>, key: string): number | null {
  const value = components[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function componentRows(components: Record<string, unknown>) {
  return Object.entries(components)
    .filter(([key, value]) => !["formula", "inputs", "methodology_version"].includes(key) && typeof value === "number")
    .slice(0, 6)
    .map(([key, value]) => ({
      key,
      label: sentenceLabel(key),
      value: value as number
    }));
}

function topGeographies(geography: BundleSummary["geography"]): BundleGeoConcentration[] {
  return [...(geography.concentrations ?? geography.municipalities ?? [])].slice(0, 6);
}

function topGeoLabel(bundle: BundleSummary): string | null {
  return topGeographies(bundle.geography)[0]?.geo_name ?? null;
}

function personRole(person: { primary_role: string | null; roles: string[]; primary_affiliation: string | null }): string {
  const role = person.primary_role ?? person.roles[0] ?? "Public lead";
  return person.primary_affiliation ? `${role} / ${person.primary_affiliation}` : role;
}

function normalizedScore(value: number): number {
  if (value <= 1) {
    return Math.max(0, value);
  }
  return Math.min(1, value / 100);
}

function formatComponentValue(value: number): string {
  if (value <= 1) {
    return formatScore(value);
  }
  return value.toLocaleString("en-CA", { maximumFractionDigits: 1 });
}

function formatPercent(value: number): string {
  return `${Math.round(normalizedScore(value) * 100)}%`;
}

function sentenceLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bIv\b/g, "IV");
}
