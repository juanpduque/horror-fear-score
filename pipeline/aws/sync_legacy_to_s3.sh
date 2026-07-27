#!/usr/bin/env bash
# Sync local legacy reviews/emotions + priority inputs to S3.
#
#   bash pipeline/aws/sync_legacy_to_s3.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUCKET="${S3_BUCKET:-horror-fear-score-102516364259}"
PREFIX="${S3_PREFIX:-hfs}"
SCRAPER_ROOT="${IMDB_SCRAPER_ROOT:-/Volumes/Adata Bituan/MacAir M1 Documentos/Pulp Analytics/Repos/IMDb-Movie-Scraper}"
REVIEWS_DIR="${SCRAPER_ROOT}/data/processed/reviews/horror_movies_backup"
EMOTIONS_DIR="${SCRAPER_ROOT}/data/processed/movie_emotions_backup"

export NO_PROXY='*'
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy || true

cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

echo "=== building id manifests $(date -u) ==="
python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, ".")
from config.paths import (
    SCRAPER_REVIEWS_DIR,
    SCRAPER_EMOTIONS_DIR,
    LEGACY_REVIEW_IDS,
    LEGACY_EMOTION_IDS,
    GAP_NEED_REVIEWS_PRIORITY,
    UNIVERSE_EN,
    COVERAGE,
    ensure_data_dirs,
)
ensure_data_dirs()

def write_ids(folder: Path, prefix: str, out: Path) -> int:
    ids = sorted(
        p.stem.replace(prefix, "")
        for p in folder.glob(f"{prefix}*.csv")
        if p.stat().st_size > 20
    )
    out.write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")
    return len(ids)

n_r = write_ids(SCRAPER_REVIEWS_DIR, "reviews_", LEGACY_REVIEW_IDS)
n_e = write_ids(SCRAPER_EMOTIONS_DIR, "emotions_", LEGACY_EMOTION_IDS)
print(f"legacy_review_ids={n_r} -> {LEGACY_REVIEW_IDS}")
print(f"legacy_emotion_ids={n_e} -> {LEGACY_EMOTION_IDS}")
for p in (GAP_NEED_REVIEWS_PRIORITY, UNIVERSE_EN, COVERAGE):
    print(f"local {'OK' if p.exists() else 'MISS'}: {p}")
PY

echo "=== upload manifests + priority $(date -u) ==="
aws s3 cp "$ROOT/data/processed/legacy_review_ids.txt" "s3://${BUCKET}/${PREFIX}/input/legacy_review_ids.txt"
aws s3 cp "$ROOT/data/processed/legacy_emotion_ids.txt" "s3://${BUCKET}/${PREFIX}/input/legacy_emotion_ids.txt"
[ -f "$ROOT/data/gaps/gap_need_reviews_priority.csv" ] && \
  aws s3 cp "$ROOT/data/gaps/gap_need_reviews_priority.csv" "s3://${BUCKET}/${PREFIX}/input/gap_need_reviews_priority.csv"
[ -f "$ROOT/data/processed/universe_en.csv" ] && \
  aws s3 cp "$ROOT/data/processed/universe_en.csv" "s3://${BUCKET}/${PREFIX}/input/universe_en.csv"
[ -f "$ROOT/data/gaps/coverage_en.csv" ] && \
  aws s3 cp "$ROOT/data/gaps/coverage_en.csv" "s3://${BUCKET}/${PREFIX}/input/coverage_en.csv"

echo "=== sync reviews (~433MB) $(date -u) ==="
if [ -d "$REVIEWS_DIR" ]; then
  aws s3 sync "$REVIEWS_DIR" "s3://${BUCKET}/${PREFIX}/legacy/reviews/" \
    --exclude "*" --include "reviews_*.csv" --size-only
else
  echo "WARN: missing $REVIEWS_DIR"
fi

echo "=== sync emotions (~443MB) $(date -u) ==="
if [ -d "$EMOTIONS_DIR" ]; then
  aws s3 sync "$EMOTIONS_DIR" "s3://${BUCKET}/${PREFIX}/legacy/emotions/" \
    --exclude "*" --include "emotions_*.csv" --size-only
else
  echo "WARN: missing $EMOTIONS_DIR"
fi

echo "=== done $(date -u) ==="
aws s3 ls "s3://${BUCKET}/${PREFIX}/input/"
echo "legacy reviews count:"
aws s3 ls "s3://${BUCKET}/${PREFIX}/legacy/reviews/" | wc -l
echo "legacy emotions count:"
aws s3 ls "s3://${BUCKET}/${PREFIX}/legacy/emotions/" | wc -l
