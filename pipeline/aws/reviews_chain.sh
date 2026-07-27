#!/usr/bin/env bash
# Fetch prioritized IMDb reviews on EC2 with Xvfb (NOT --headless).
# Layout: ~/hfs/{pipeline,config,data,...}
#
#   bash pipeline/aws/reviews_chain.sh
set -euo pipefail
HOME_DIR="${HFS_HOME:-${HOME}/hfs}"
BUCKET="${S3_BUCKET:-horror-fear-score-102516364259}"
PREFIX="${S3_PREFIX:-hfs}"
LOG="${HOME_DIR}/data/raw/reviews_fetch_aws.log"
DONE="${HOME_DIR}/data/raw/REVIEWS_FETCH_DONE"
LIMIT="${LIMIT:-}"          # empty = all pending
SLEEP="${SLEEP:-2.0}"

mkdir -p "${HOME_DIR}/data/raw/reviews" "${HOME_DIR}/logs"
exec > >(tee -a "$LOG") 2>&1

echo "=== reviews_chain start $(date -u) ==="
cd "$HOME_DIR"

export NO_PROXY='*'
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy || true

# Virtual display — Chrome runs headed against Xvfb
if ! pgrep -x Xvfb >/dev/null 2>&1; then
  Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
  sleep 1
fi
export DISPLAY=:99
echo "DISPLAY=$DISPLAY"
google-chrome --version || true

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip -q install -U pip
pip -q install -r requirements.txt

echo "=== pull inputs from S3 ==="
aws s3 cp "s3://${BUCKET}/${PREFIX}/input/gap_need_reviews_priority.csv" \
  data/gaps/gap_need_reviews_priority.csv
aws s3 cp "s3://${BUCKET}/${PREFIX}/input/legacy_review_ids.txt" \
  data/processed/legacy_review_ids.txt
mkdir -p data/gaps data/processed data/raw/reviews

# Resume: pull any reviews already scraped in this work prefix
aws s3 sync "s3://${BUCKET}/${PREFIX}/work/reviews/" data/raw/reviews/ \
  --exclude "*" --include "reviews_*.csv" --size-only || true

# S3 watch in background
if [ ! -f data/raw/reviews_s3_watch.pid ] || ! kill -0 "$(cat data/raw/reviews_s3_watch.pid)" 2>/dev/null; then
  nohup bash pipeline/aws/reviews_s3_watch.sh >/dev/null 2>&1 &
  echo $! > data/raw/reviews_s3_watch.pid
  echo "s3 watch pid=$(cat data/raw/reviews_s3_watch.pid)"
fi

ARGS=(
  --priority data/gaps/gap_need_reviews_priority.csv
  --out-dir data/raw/reviews
  --skip-ids-file data/processed/legacy_review_ids.txt
  --sleep "$SLEEP"
  --s3-uri "s3://${BUCKET}/${PREFIX}/work/reviews"
)
if [ -n "$LIMIT" ]; then
  ARGS+=(--limit "$LIMIT")
fi

echo "=== fetch start args=${ARGS[*]} ==="
python3 -u pipeline/fetch_imdb_reviews.py "${ARGS[@]}"

date -u +"REVIEWS_FETCH_DONE_%Y%m%dT%H%M%SZ" > "$DONE"
echo "=== reviews_chain done $(date -u) ==="
