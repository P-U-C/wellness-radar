import { BarChart3, Globe2, MapPin, Sparkles, TrendingUp, UserRound, Users } from "lucide-react";
import { ConfidenceBar } from "../../components";
import type {
  BundleDetail,
  BundleGeoConcentration,
  BundleSummary,
  DailyBrief,
  FirstMoverCity,
  OpportunityProposition,
  WorldwideMatch
} from "../../lib/api";
import { formatScore } from "../../lib/format";
import { TodayBriefPanel } from "../brief/TodayBriefPanel";

type BundleRailProps = {
  bundles: BundleSummary[];
  selectedBundleId: string | null;
  mappedPlaceCount: number;
  totalPlaceCount: number;
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
  brief: DailyBrief | null;
  briefLoading: boolean;
  briefError: string | null;
  propositions: OpportunityProposition[];
};

export function BundleRail({
  bundles,
  selectedBundleId,
  mappedPlaceCount,
  totalPlaceCount,
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
            showing {mappedPlaceCount} of {totalPlaceCount}
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
  omittedPlaceCount,
  brief,
  briefLoading,
  briefError,
  propositions
}: BundleDetailPanelProps) {
  if (!bundle) {
    return (
      <aside className="wr-bundle-detail-panel" aria-label="Today's findings">
        <TodayBriefPanel brief={brief} loading={briefLoading} error={briefError} />
        <div className="wr-bundle-detail-section">
          <h3>
            <Sparkles size={15} />
            Top opportunities we found
          </h3>
          <div className="wr-home-propositions">
            {propositions.slice(0, 4).map((proposition) => (
              <article key={proposition.id}>
                <div className="wr-home-prop-head">
                  <strong>{proposition.headline}</strong>
                  <span>{proposition.geo_name}</span>
                </div>
                <p>{proposition.thesis ?? proposition.summary}</p>
                <ConfidenceBar score={proposition.confidence_score} />
              </article>
            ))}
            {propositions.length === 0 ? (
              <p className="wr-bundle-empty">No source-backed opportunities yet.</p>
            ) : null}
          </div>
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
  const worldwide = detail?.worldwide_match ?? null;
  const firstMovers = detail?.first_mover_cities ?? [];
  const firstMoverStatus = detail?.first_mover_cities_status ?? null;
  const worldwidePending =
    worldwide?.source_status === "data_pending" || worldwide?.source_status === "fixture_fallback";
  const firstMoversPending =
    firstMoverStatus?.status === "data_pending" || firstMovers.some((city) => city.source_status === "fixture_fallback");
  const trendingLabel = formatPercent(numberComponent(bundle.components, "momentum") ?? bundle.score);

  return (
    <aside className="wr-bundle-detail-panel" aria-label="Selected bundle details">
      <div className="wr-bundle-detail-head">
        <span>SELECTED BUNDLE</span>
        <h2>{bundle.label}</h2>
        <strong>{formatScore(bundle.score)}</strong>
      </div>

      <div className="wr-bundle-detail-section wr-answer" data-q="1">
        <h3>
          <TrendingUp size={15} />
          <span className="wr-answer-q">Is it trending here?</span>
          <b className="wr-answer-tag">{trendingLabel} momentum</b>
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

      <div className="wr-bundle-detail-section wr-answer" data-q="2">
        <h3>
          <MapPin size={15} />
          <span className="wr-answer-q">What's available, and where?</span>
          <b className="wr-answer-tag">{bundle.member_count} places</b>
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

      <div className="wr-bundle-detail-section wr-answer" data-q="3">
        <h3>
          <UserRound size={15} />
          <span className="wr-answer-q">Who's driving it?</span>
          <b className="wr-answer-tag">{topPeople.length} people</b>
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

      <div className="wr-bundle-detail-section wr-answer" data-q="4">
        <h3>
          <Globe2 size={15} />
          <span className="wr-answer-q">Does it match a worldwide trend?</span>
          {worldwide ? (
            <b className={`wr-answer-tag ${worldwidePending ? "is-pending" : ""}`}>
              {verdictLabel(worldwide.verdict)}
            </b>
          ) : null}
        </h3>
        {worldwide ? (
          <div className="wr-worldwide">
            <p className="wr-worldwide-verdict">{worldwideNarrative(worldwide)}</p>
            <ConfidenceBar score={worldwide.confidence_score} label="GLOBAL" />
          </div>
        ) : (
          <p>No worldwide signal computed for this bundle yet.</p>
        )}
      </div>

      <div className="wr-bundle-detail-section wr-answer" data-q="5">
        <h3>
          <Globe2 size={15} />
          <span className="wr-answer-q">What do first-mover cities show?</span>
          <b className={`wr-answer-tag ${firstMoversPending ? "is-pending" : ""}`}>
            {firstMovers.length > 0 ? `${firstMovers.length} cities` : firstMoverStatusLabel(firstMoverStatus)}
          </b>
        </h3>
        <div className="wr-geo-list">
          {firstMovers.slice(0, 6).map((city) => (
            <div key={city.city}>
              <span>{city.city}</span>
              <b>
                {firstMoverLabel(city)}
                {city.source_status === "fixture_fallback" ? (
                  <em className="wr-fixture-flag" title="Benchmark fixture, not a live feed">
                    fixture
                  </em>
                ) : null}
              </b>
            </div>
          ))}
          {firstMovers.length === 0 ? (
            <p>{firstMoverStatus?.reason ?? "No first-mover city data yet."}</p>
          ) : null}
        </div>
        {firstMoverStatus?.hidden_fixture_count ? (
          <p className="wr-fixture-note">
            Fixture benchmark rows are hidden until live or cached aggregate city counts are available.
          </p>
        ) : null}
      </div>
    </aside>
  );
}

function verdictLabel(verdict: string): string {
  return verdict.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function worldwideNarrative(match: WorldwideMatch): string {
  if (match.source_status === "data_pending") {
    const reason = typeof match.components?.reason === "string"
      ? match.components.reason
      : "Worldwide trend evidence has not been computed for this bundle.";
    return `Worldwide trend match is data pending. ${reason}`;
  }
  const direction =
    match.direction === "rising"
      ? "rising"
      : match.direction === "cooling"
        ? "cooling"
        : "flat";
  const spread = match.components?.cities_with_supply;
  const spreadText =
    typeof spread === "number" ? ` Supplied in ${spread} of the benchmark cities.` : "";
  const status =
    match.source_status === "cached"
      ? " (cached source data)"
      : match.source_status === "fixture_fallback"
        ? " (fallback data hidden from decisions)"
        : "";
  return `Global attention is ${direction}; verdict: ${match.verdict}.${spreadText}${status}`;
}

function firstMoverStatusLabel(status: BundleDetail["first_mover_cities_status"]): string {
  if (!status || status.status === "data_pending") {
    return "Data Pending";
  }
  return status.status === "cached" ? "Cached" : "Live";
}

function firstMoverLabel(city: FirstMoverCity): string {
  const ratio = city.ratio_vs_vancouver;
  if (!Number.isFinite(ratio) || ratio <= 0) {
    return `${city.count} places`;
  }
  return `${city.count} places / ${ratio.toFixed(1)}x vs Van`;
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
