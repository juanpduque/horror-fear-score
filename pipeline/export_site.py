"""Export site-ready JSON/CSV for the narrative piece (fase 2 stub)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.paths import EXPORTS_DIR, FEAR_SCORES, ensure_data_dirs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export fear scores for the site (fase 2)."
    )
    parser.add_argument("--input", type=Path, default=FEAR_SCORES)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument(
        "--out",
        type=Path,
        default=EXPORTS_DIR / "fear_scores_top.json",
    )
    args = parser.parse_args()

    ensure_data_dirs()
    if not args.input.exists():
        raise FileNotFoundError(
            f"Missing {args.input}. Run compute_fear_score.py first."
        )

    df = pd.read_csv(args.input).head(args.top)
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out} ({len(records)} records)")


if __name__ == "__main__":
    main()
