"""Fetch IMDb reviews for the prioritized gap (batch, resumable).

Reads gap_need_reviews_priority.csv, scrapes review text via Selenium,
writes data/raw/reviews/reviews_{imdb_id}.csv (column: Review).

Notes:
- Prefer headed Chrome (IMDb often challenges headless).
- Skips IDs that already have a non-empty reviews_*.csv in --out-dir
  or in the legacy scraper reviews folder.
- Use --limit for pilot runs.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.paths import (  # noqa: E402
    GAP_NEED_REVIEWS_PRIORITY,
    PROJECT_ROOT,
    RAW_REVIEWS_DIR,
    SCRAPER_REVIEWS_DIR,
    ensure_data_dirs,
)

LOG_DIR = PROJECT_ROOT / "logs"


def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "fetch_imdb_reviews.log"),
        ],
    )


def _existing_review_ids(*dirs: Path) -> set[str]:
    found: set[str] = set()
    for d in dirs:
        if not d or not d.exists():
            continue
        for p in d.glob("reviews_*.csv"):
            if p.stat().st_size > 20:  # more than empty/header-ish
                found.add(p.stem.replace("reviews_", ""))
    return found


def _build_driver(headless: bool):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1400,1000")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)


def scrape_reviews_for_id(driver, imdb_id: str, pause: float = 1.5) -> list[str]:
    """Scrape visible review bodies from IMDb reviews page."""
    from bs4 import BeautifulSoup
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    url = f"https://www.imdb.com/title/{imdb_id}/reviews/?sort=submissionDate&dir=desc"
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.ipc-html-content-inner-div, .text.show-more__control")
            )
        )
    except TimeoutException:
        # Older markup fallback wait
        time.sleep(2)

    # Expand "All" / load more if present (best-effort)
    for selector in [
        "button.ipc-see-more__button",
        "button[data-testid='pagination-button']",
        ".ipl-load-more__button",
    ]:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            clicks = 0
            while buttons and clicks < 40:
                buttons[0].click()
                clicks += 1
                time.sleep(pause)
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            pass

    soup = BeautifulSoup(driver.page_source, "html.parser")
    texts: list[str] = []
    for sel in (
        "div.ipc-html-content-inner-div",
        "div.text.show-more__control",
        "div.content .text",
    ):
        for el in soup.select(sel):
            t = el.get_text(" ", strip=True)
            if t and len(t) > 20:
                texts.append(t)
        if texts:
            break

    # de-dupe preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def save_reviews(imdb_id: str, reviews: list[str], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"reviews_{imdb_id}.csv"
    pd.DataFrame({"Review": reviews}).to_csv(path, index=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch IMDb reviews for prioritized gap (resumable)."
    )
    parser.add_argument(
        "--priority",
        type=Path,
        default=GAP_NEED_REVIEWS_PRIORITY,
    )
    parser.add_argument("--out-dir", type=Path, default=RAW_REVIEWS_DIR)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=2.0)
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Use headless Chrome (often blocked by IMDb).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List pending IDs without scraping.",
    )
    parser.add_argument(
        "--ignore-legacy",
        action="store_true",
        help="Do not skip IDs already present in legacy scraper folder.",
    )
    args = parser.parse_args()

    _setup_logging()
    ensure_data_dirs()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if not args.priority.exists():
        raise FileNotFoundError(
            f"Missing {args.priority}. Run build_reviews_priority.py first."
        )

    pri = pd.read_csv(args.priority)
    if "imdb_id" not in pri.columns:
        raise ValueError("priority CSV needs imdb_id")

    legacy = None if args.ignore_legacy else SCRAPER_REVIEWS_DIR
    already = _existing_review_ids(args.out_dir, legacy)
    pending = pri[~pri["imdb_id"].astype(str).isin(already)].copy()
    pending = pending.iloc[args.offset :]
    if args.limit is not None:
        pending = pending.head(args.limit)

    logging.info(
        "Priority %d | already have reviews %d | pending this run %d",
        len(pri),
        len(already),
        len(pending),
    )

    if args.dry_run:
        cols = [
            c
            for c in ["priority_rank", "title", "year", "vote_count", "imdb_id"]
            if c in pending.columns
        ]
        print(pending[cols].to_string(index=False))
        print(f"\nDry run: {len(pending)} pending")
        return

    if pending.empty:
        logging.info("Nothing to fetch.")
        return

    driver = _build_driver(headless=args.headless)
    progress_rows: list[dict] = []
    try:
        for i, row in enumerate(pending.itertuples(index=False), start=1):
            imdb_id = str(row.imdb_id)
            title = getattr(row, "title", "")
            logging.info("[%d/%d] %s %s", i, len(pending), imdb_id, title)
            try:
                reviews = scrape_reviews_for_id(driver, imdb_id)
                if not reviews:
                    logging.warning("No reviews extracted for %s", imdb_id)
                    progress_rows.append(
                        {
                            "imdb_id": imdb_id,
                            "title": title,
                            "n_reviews": 0,
                            "status": "empty",
                        }
                    )
                else:
                    path = save_reviews(imdb_id, reviews, args.out_dir)
                    logging.info("Saved %d reviews → %s", len(reviews), path)
                    progress_rows.append(
                        {
                            "imdb_id": imdb_id,
                            "title": title,
                            "n_reviews": len(reviews),
                            "status": "ok",
                        }
                    )
            except Exception as e:
                logging.exception("Failed %s: %s", imdb_id, e)
                progress_rows.append(
                    {
                        "imdb_id": imdb_id,
                        "title": title,
                        "n_reviews": 0,
                        "status": f"error:{type(e).__name__}",
                    }
                )
            time.sleep(args.sleep)
    finally:
        driver.quit()
        prog = args.out_dir.parent / "fetch_reviews_progress.csv"
        pd.DataFrame(progress_rows).to_csv(prog, index=False)
        logging.info("Progress written to %s", prog)


if __name__ == "__main__":
    main()
