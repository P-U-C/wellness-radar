import { ConfidenceBar, EntityBadge, RangeSlider, SignalCard, SourceChip } from "../../components";
import type { Signal, SourceRef } from "../../lib/api";
import { entity, MAGMA, mapStyle, surfaces, text, trustTier } from "../../lib/theme";

const TRUST_TIERS = [
  "official",
  "reputable_press",
  "commercial_api",
  "community",
  "informal",
  "ai_inferred"
];

const sampleRefs: SourceRef[] = TRUST_TIERS.map((tier) => ({
  source_name: tier,
  url: null,
  trust_tier: tier,
  seen_at: new Date().toISOString(),
  source_record_id: `sample_${tier}`,
  licence: "design reference"
}));

const sampleSignal: Signal = {
  id: "system_signal",
  type: "new_operator",
  severity: "info",
  title: "Othership files second-location permit",
  summary: "A source-backed signal rendered by the reusable SignalCard component.",
  why_it_matters:
    "Expansion into a dense recovery corridor changes the local competitive set and raises confidence in the category velocity signal.",
  source_name: "City of Vancouver",
  source_url: null,
  trust_tier: "official",
  occurred_at: new Date().toISOString(),
  lat: 49.263,
  lng: -123.102,
  related_operator_id: null,
  confidence_score: 0.9,
  source_refs: [sampleRefs[0]],
  freshness_age_hours: 3
};

export function SystemScreen() {
  return (
    <section className="wr-system-screen" aria-label="Luminous design system">
      <div className="wr-system-inner">
        <header>
          <span>DESIGN SYSTEM</span>
          <h1>Luminous / Wellness Radar instrument system</h1>
          <p>
            Dark base, per-entity accents, magma data heat, provenance-first records, and mono numerics across every
            analytical surface.
          </p>
        </header>

        <section className="wr-system-section">
          <h2>01 / Color Tokens</h2>
          <h3>SURFACES</h3>
          <div className="wr-token-grid">
            {Object.entries(surfaces).map(([name, color]) => (
              <TokenSwatch key={name} name={name} color={color} />
            ))}
            <TokenSwatch name="text" color={text.primary} />
          </div>
          <h3>ENTITY ACCENTS</h3>
          <div className="wr-token-grid is-entity">
            <TokenSwatch name="operator" color={entity.operator} />
            <TokenSwatch name="signal" color={entity.signal} />
            <TokenSwatch name="people" color={entity.people} />
            <TokenSwatch name="opportunity" color={entity.opportunity} />
          </div>
          <h3>MAGMA SCORE RAMP</h3>
          <div className="wr-magma-reference" />
          <div className="wr-magma-labels">
            <span>0.0 / {MAGMA[0]}</span>
            <span>0.5 / {MAGMA[3]}</span>
            <span>1.0 / {MAGMA[5]}</span>
          </div>
        </section>

        <section className="wr-system-section">
          <h2>02 / Type Scale</h2>
          <div className="wr-type-sheet">
            <div>
              <strong>Display 34/700</strong>
              <span>Grotesk / screen titles</span>
            </div>
            <div>
              <b>Heading 21/700</b>
              <span>entity names</span>
            </div>
            <div>
              <em>Body 15/600 and 13/400</em>
              <span>cards, descriptions</span>
            </div>
            <div>
              <code>Mono 12/500 / 49.2827N / conf 0.92 / 3h</code>
              <span>all numerics, coords, IDs</span>
            </div>
          </div>
        </section>

        <section className="wr-system-section">
          <h2>03 / Component Library</h2>
          <div className="wr-component-grid">
            <article>
              <h3>SOURCE CHIP / 6 TRUST TIERS</h3>
              <div className="wr-system-chip-row">
                {sampleRefs.map((ref) => (
                  <SourceChip key={ref.trust_tier} refData={ref} compact />
                ))}
              </div>
            </article>
            <article>
              <h3>CONFIDENCE INDICATOR</h3>
              <ConfidenceBar score={0.92} />
              <ConfidenceBar score={0.66} />
              <ConfidenceBar score={0.38} />
            </article>
            <article>
              <h3>FEED ITEM</h3>
              <SignalCard signal={sampleSignal} variant="stream" context="Mount Pleasant" actionLabel="fly to" />
            </article>
            <article>
              <h3>CONTROLS</h3>
              <div className="wr-system-controls">
                <EntityBadge type="operator" label="OPERATOR" />
                <EntityBadge type="signal" label="SIGNAL" />
                <EntityBadge type="people" label="PEOPLE" />
                <EntityBadge type="opportunity" label="OPPORTUNITY" />
              </div>
              <RangeSlider label="MIN CONFIDENCE" value={0.6} color="ok" onChange={() => undefined} />
            </article>
          </div>
        </section>

        <section className="wr-system-section">
          <h2>04 / Map Style</h2>
          <div className="wr-map-token-grid">
            <TokenSwatch name="land" color={mapStyle.land} />
            <TokenSwatch name="water" color={mapStyle.water} />
            <TokenSwatch name="graticule" color={mapStyle.graticule} />
            <TokenSwatch name="pin" color={mapStyle.pin} />
            <div>
              <span>hex fill opacity</span>
              <strong>{mapStyle.hexFillOpacity(0.72).toFixed(2)}</strong>
            </div>
            <div>
              <span>trust tiers</span>
              <strong>{Object.keys(trustTier).length}</strong>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

function TokenSwatch({ name, color }: { name: string; color: string }) {
  return (
    <div className="wr-token-swatch">
      <i style={{ background: color }} />
      <span>{name}</span>
      <b>{color}</b>
    </div>
  );
}
