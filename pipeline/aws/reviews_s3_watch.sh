#!/usr/bin/env bash
# Periodic S3 checkpoint for IMDb reviews fetch on EC2.
#   INTERVAL=120 bash pipeline/aws/reviews_s3_watch.sh
set -euo pipefail
BUCKET="${S3_BUCKET:-horror-fear-score-102516364259}"
PREFIX="${S3_PREFIX:-hfs}"
INTERVAL="${INTERVAL:-120}"
HOME_DIR="${HFS_HOME:-${HOME}/hfs}"
REVIEWS="${HOME_DIR}/data/raw/reviews"
DONE="${HOME_DIR}/data/raw/REVIEWS_FETCH_DONE"
WLOG="${HOME_DIR}/data/raw/reviews_s3_watch.log"
PROGRESS="${HOME_DIR}/data/raw/fetch_reviews_progress.csv"

mkdir -p "$REVIEWS" "$(dirname "$WLOG")"
exec >>"$WLOG" 2>&1
echo "=== reviews s3 watch start $(date -u) s3://${BUCKET}/${PREFIX}/ ==="

upload() {
  local stamp
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  aws s3 sync "$REVIEWS" "s3://${BUCKET}/${PREFIX}/work/reviews/" \
    --exclude "*" --include "reviews_*.csv" --size-only --quiet || true
  if [ -f "$PROGRESS" ]; then
    aws s3 cp "$PROGRESS" "s3://${BUCKET}/${PREFIX}/latest/fetch_reviews_progress.csv" --quiet || true
    aws s3 cp "$PROGRESS" "s3://${BUCKET}/${PREFIX}/checkpoints/${stamp}/fetch_reviews_progress.csv" --quiet || true
  fi
  echo "checkpoint ${stamp}"
}

while [ ! -f "$DONE" ]; do
  upload
  sleep "$INTERVAL"
done

upload
aws s3 cp "$DONE" "s3://${BUCKET}/${PREFIX}/latest/REVIEWS_FETCH_DONE" --quiet || true
echo "=== reviews s3 watch done $(date -u) ==="
