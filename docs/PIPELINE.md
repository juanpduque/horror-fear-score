# Horror Fear Score — pipeline notes

## Why TMDB for language

IMDb `title.akas` language coverage is incomplete (~half marked; many `\N`).
TMDB `original_language` is the filter of record for this project.

Source catalog: Anatomy of Fear `pipeline/data/horror_movies.csv`
(plus `imdb_ids.csv` and exclusion CSVs).

## Stages

1. `build_universe.py` — EN horror after exclusions → `data/processed/universe_en.csv`
2. `inventory_coverage.py` — join to legacy reviews/emotions → gap CSVs
3. `build_reviews_priority.py` — features + vote floor → `data/gaps/gap_need_reviews_priority.csv`
4. `fetch_imdb_reviews.py` — Selenium batch scrape → `data/raw/reviews/reviews_*.csv`
5. `compute_fear_score.py` — aggregate fear from emotion files → `data/exports/fear_scores.csv`
6. `export_site.py` — thin JSON for the narrative site (fase 2)

### Reviews gap strategy

Do **not** scrape the full `gap_need_reviews` (~13k). Most titles have TMDB
`vote_count < 10` or are shorts. Priority queue defaults:

- `runtime >= 41` (exclude shorts ≤40)
- `vote_count >= 100` (~370 features)
- sort by `vote_count`, then `popularity`

```bash
python pipeline/build_reviews_priority.py
python pipeline/fetch_imdb_reviews.py --dry-run
python pipeline/fetch_imdb_reviews.py --limit 5   # pilot (headed Chrome)
```

Prefer headed Chrome; headless is often challenged by IMDb.

## AWS (EC2 + S3)

Bucket: `s3://horror-fear-score-102516364259/hfs/`

| Prefijo | Contenido |
|---------|-----------|
| `input/` | priority CSV, legacy id manifests, universe |
| `legacy/reviews/` | reseñas ya scrapeadas (~17k) |
| `legacy/emotions/` | emociones ya calculadas (~17k) |
| `work/reviews/` | reseñas nuevas del worker EC2 |
| `latest/` | progress / DONE markers |

```bash
# 1) Subir disco → S3 (~900MB; puede tardar)
bash pipeline/aws/sync_legacy_to_s3.sh

# 2) Lanzar EC2 (Xvfb + Chrome headed) para la cola prioritaria
bash pipeline/aws/launch_reviews_ec2.sh
# piloto: LIMIT=10 bash pipeline/aws/launch_reviews_ec2.sh
```

Reusa SG/key/IAM de `aof-imdb-selenium`. Costo aprox: t3.medium ~USD 0.04/h + S3 negligible.
No termina la instancia AOF de enrich de IDs (`aof-imdb-selenium`); lanza una aparte (`hfs-imdb-reviews`).


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
