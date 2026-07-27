"""Build English-language horror universe from TMDB (via AOF catalog).

IMDb does not reliably expose original language; we use TMDB
`original_language == en`, then apply AOF exclusion lists and join imdb_ids.
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
    AOF_EXCLUDED_ANIMATION,
    AOF_EXCLUDED_MUSIC,
    AOF_EXCLUDED_NON_ENGLISH,
    AOF_HORROR_MOVIES,
    AOF_IMDB_IDS,
    UNIVERSE_EN,
    ensure_data_dirs,
)


KEEP_COLS = [
    "id",
    "title",
    "original_title",
    "original_language",
    "release_date",
    "runtime",
    "vote_average",
    "vote_count",
    "popularity",
    "genre_names",
    "poster_path",
    "overview",
]


def _load_exclusion_ids(path: Path) -> set[int]:
    if not path.exists():
        raise FileNotFoundError(f"Missing exclusion file: {path}")
    df = pd.read_csv(path)
    if "id" not in df.columns:
        raise ValueError(f"Expected 'id' column in {path}")
    return set(df["id"].dropna().astype(int))


def build_universe(
    horror_movies: Path = AOF_HORROR_MOVIES,
    imdb_ids: Path = AOF_IMDB_IDS,
    language: str = "en",
) -> pd.DataFrame:
    if not horror_movies.exists():
        raise FileNotFoundError(
            f"TMDB horror catalog not found: {horror_movies}\n"
            "Set AOF_ROOT in .env to your anatomy-of-fear checkout."
        )
    if not imdb_ids.exists():
        raise FileNotFoundError(f"IMDb map not found: {imdb_ids}")

    hm = pd.read_csv(horror_movies, low_memory=False)
    required = {"id", "original_language"}
    missing = required - set(hm.columns)
    if missing:
        raise ValueError(f"horror_movies.csv missing columns: {missing}")

    en = hm[hm["original_language"].astype(str).str.lower() == language].copy()

    excluded = (
        _load_exclusion_ids(AOF_EXCLUDED_ANIMATION)
        | _load_exclusion_ids(AOF_EXCLUDED_MUSIC)
        | _load_exclusion_ids(AOF_EXCLUDED_NON_ENGLISH)
    )
    en = en[~en["id"].astype(int).isin(excluded)].copy()

    # Prefer dedicated AOF imdb map over any column already on the catalog.
    id_map = pd.read_csv(imdb_ids)
    if not {"id", "imdb_id"}.issubset(id_map.columns):
        raise ValueError("imdb_ids.csv must have columns: id, imdb_id")

    base_cols = [c for c in KEEP_COLS if c in en.columns]
    universe = en[base_cols].drop_duplicates(subset=["id"])
    universe = universe.merge(id_map[["id", "imdb_id"]], on="id", how="left")

    # Normalize imdb_id
    universe["imdb_id"] = (
        universe["imdb_id"]
        .astype(str)
        .str.strip()
        .replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
    )
    universe.loc[
        ~universe["imdb_id"].fillna("").str.startswith("tt"), "imdb_id"
    ] = pd.NA

    if "release_date" in universe.columns:
        universe["year"] = pd.to_datetime(
            universe["release_date"], errors="coerce"
        ).dt.year
    else:
        universe["year"] = pd.NA

    universe = universe.sort_values(["year", "title"], na_position="last")
    return universe.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build EN horror universe from TMDB (AOF catalog)."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=UNIVERSE_EN,
        help="Output CSV path",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="TMDB original_language code (default: en)",
    )
    args = parser.parse_args()

    ensure_data_dirs()
    universe = build_universe(language=args.language.lower())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(args.out, index=False)

    n = len(universe)
    with_imdb = universe["imdb_id"].notna().sum()
    print(f"Wrote {args.out}")
    print(f"  titles:           {n}")
    print(f"  with imdb_id:     {with_imdb}")
    print(f"  missing imdb_id:  {n - with_imdb}")


if __name__ == "__main__":
    main()
