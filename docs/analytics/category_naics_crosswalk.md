# Category Enum and Draft NAICS Crosswalk

Status: needs-human-review

The category enum is frozen for M3 analytics and matches `AGENT_SPEC.md` section 4:

- `recovery_contrast_therapy`
- `fitness_movement`
- `mind_meditation`
- `spa_thermal`
- `aesthetics_medspa`
- `nutrition_longevity`
- `allied_health`
- `womens_health`
- `social_hospitality`
- `recovery_modalities`
- `preventive_diagnostic`
- `mental_health`
- `community_social_wellness`
- `wellness_retail_product`

The database enforces this enum for `operator.categories` through migration `004_m3_intelligence_beta.sql`.

## Draft NAICS Mappings

These mappings unblock denominator joins for M3, but they are not legal/statistical sign-off.

| Category | NAICS | Label | Match | Review note |
|---|---:|---|---|---|
| `recovery_contrast_therapy` | 812190 | Other personal care services | Primary | StatCan examples include saunas and bath houses; confirm classification for modern recovery clubs. |
| `recovery_contrast_therapy` | 713940 | Fitness and recreational sports centres | Secondary | Some recovery clubs may be coded as fitness/recreation facilities. |
| `fitness_movement` | 713940 | Fitness and recreational sports centres | Primary | Primary business-count denominator for gyms and fitness facilities. |
| `mind_meditation` | 611690 | All other schools and instruction | Secondary | Class-based meditation/breathwork may map here. |
| `spa_thermal` | 812190 | Other personal care services | Primary | Spa, sauna, bathhouse, massage, and thermal services overlap this code. |
| `aesthetics_medspa` | 812190 | Other personal care services | Secondary | Broad personal-care proxy only; procedure-level demand or regulated status is not inferred from NAICS. |
| `recovery_modalities` | 713940 | Fitness and recreational sports centres | Secondary | Athlete recovery modalities often co-locate with fitness/recreation but require source text evidence. |
| `nutrition_longevity` | 621390 | Offices of all other health practitioners | Secondary | Practitioner-led services only; product retail maps separately. |
| `allied_health` | 621340 | Offices of physical, occupational, and speech therapists and audiologists | Primary | Includes physiotherapy/kinesiology-style private practice examples. |
| `allied_health` | 621390 | Offices of all other health practitioners | Secondary | Catch-all for other practitioner offices. |
| `womens_health` | 621410 | Family planning centres | Secondary | The category is broader than this NAICS code. |
| `social_hospitality` | 813410 | Civic and social organizations | Secondary | Sober-social/cafe/coworking wellness concepts are mixed hospitality/community models; plain cafes are not included. |
| `preventive_diagnostic` | 621510 | Medical and diagnostic laboratories | Primary | Lab/diagnostic denominator. |
| `mental_health` | 621330 | Offices of mental health practitioners, except physicians | Primary | Counselling/psychology/psychotherapy denominator. |
| `community_social_wellness` | 813410 | Civic and social organizations | Secondary | Useful for community models; commercial venues may map elsewhere. |
| `wellness_retail_product` | 456191 | Food (health) supplement stores | Primary | Retail health-product storefront denominator where available. |

## Source Notes

- Statistics Canada WDS documentation: `https://www.statcan.gc.ca/en/developers/wds`
- Statistics Canada WDS user guide: `https://www.statcan.gc.ca/en/developers/wds/user-guide`
- Statistics Canada NAICS 2022 pages are referenced per row in `naics_category_crosswalk.source_refs`.

## Human Review Checklist

- Confirm the final NAICS version and whether 2022 codes should be backcast for business-count tables.
- Confirm whether category-to-NAICS joins should use primary mappings only or primary plus secondary.
- Confirm attribution language and permitted UI display for NAICS/business-count denominators.
- Confirm whether ambiguous categories need per-source override rules before production.
