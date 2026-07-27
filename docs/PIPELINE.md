# Horror Fear Score — pipeline notes

## Why TMDB for language

IMDb `title.akas` language coverage is incomplete (~half marked; many `\N`).
TMDB `original_language` is the filter of record for this project.

Source catalog: Anatomy of Fear `pipeline/data/horror_movies.csv`
(plus `imdb_ids.csv` and exclusion CSVs).

## Stages

1. `build_universe.py` — EN horror after exclusions → `data/processed/universe_en.csv`
2. `inventory_coverage.py` — join to legacy reviews/emotions → gap CSVs
3. `compute_fear_score.py` — aggregate fear from emotion files → `data/exports/fear_scores.csv`
4. `export_site.py` — thin JSON for the narrative site (fase 2)

## External data (not in git)

| Path env | Role |
|----------|------|
| `AOF_ROOT` | TMDB catalog + id map + exclusions |
| `IMDB_SCRAPER_ROOT` | Existing review + emotion CSVs (~2GB) |

## Fear score v1

- Model (legacy): `j-hartmann/emotion-english-distilroberta-base`
- Per film: mean score among reviews labeled `fear`
- Shrinkage: `avg * n / (n + k)` with `n = fear_count` (also export legacy_n variant)
- Default `--min-reviews 5`

Revisit formula before locking the public ranking (fear_share vs confidence, etc.).
