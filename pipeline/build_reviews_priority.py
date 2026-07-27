"""Build a prioritized reviews gap from gap_need_reviews.csv.

Default: feature-length (runtime > 40), TMDB vote_count >= --min-votes,
sorted by vote_count then popularity. Writes gap_need_reviews_priority.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.paths import (  # noqa: E402
    GAP_NEED_REVIEWS,
    GAP_NEED_REVIEWS_PRIORITY,
    ensure_data_dirs,
)


def build_priority(
    gap_path: Path = GAP_NEED_REVIEWS,
    min_votes: int = 100,
    min_runtime: int = 41,
    max_rows: int | None = None,
) -> pd.DataFrame:
    if not gap_path.exists():
        raise FileNotFoundError(
            f"Missing {gap_path}. Run inventory_coverage.py first."
        )

    gap = pd.read_csv(gap_path)
    if "imdb_id" not in gap.columns:
        raise ValueError("gap CSV must include imdb_id")

    out = gap[gap["imdb_id"].notna()].copy()
    out["runtime"] = pd.to_numeric(out.get("runtime"), errors="coerce")
    out["vote_count"] = pd.to_numeric(out.get("vote_count"), errors="coerce").fillna(0)
    out["popularity"] = pd.to_numeric(out.get("popularity"), errors="coerce").fillna(0)

    out = out[out["runtime"].fillna(0) >= min_runtime]
    out = out[out["vote_count"] >= min_votes]
    out = out.sort_values(
        ["vote_count", "popularity"], ascending=False
    ).reset_index(drop=True)
    out["priority_rank"] = out.index + 1

    if max_rows is not None:
        out = out.head(max_rows)

    keep = [
        c
        for c in [
            "priority_rank",
            "id",
            "imdb_id",
            "title",
            "year",
            "runtime",
            "vote_count",
            "popularity",
            "vote_average",
            "genre_names",
            "status",
        ]
        if c in out.columns
    ]
    return out[keep]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build prioritized reviews gap (features + vote floor)."
    )
    parser.add_argument("--gap", type=Path, default=GAP_NEED_REVIEWS)
    parser.add_argument("--out", type=Path, default=GAP_NEED_REVIEWS_PRIORITY)
    parser.add_argument("--min-votes", type=int, default=100)
    parser.add_argument(
        "--min-runtime",
        type=int,
        default=41,
        help="Minimum runtime minutes (default 41 = exclude shorts ≤40)",
    )
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    ensure_data_dirs()
    priority = build_priority(
        gap_path=args.gap,
        min_votes=args.min_votes,
        min_runtime=args.min_runtime,
        max_rows=args.max_rows,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    priority.to_csv(args.out, index=False)

    print(f"Wrote {args.out} ({len(priority)} films)")
    if not priority.empty:
        print(priority.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
