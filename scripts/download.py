"""
הורדת קבצי מחירים ומבצעים מהרשתות (לפי חוק שקיפות המחירים).
Downloads PriceFull / PromoFull / Stores files for the chains in config.json
into dumps/<chain_id>/ using the open-source il-supermarket-scraper package.

Usage:  python scripts/download.py            (all enabled chains)
        python scripts/download.py rami osher (only these chain ids)
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from il_supermarket_scarper import ScraperFactory
from il_supermarket_scarper.utils import DiskFileOutput

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DUMPS = ROOT / "dumps"


async def collect(scraper, **kwargs):
    names = []
    try:
        async for result in scraper.scrape(**kwargs):
            name = getattr(result, "file_name", None)
            ok = getattr(result, "extract_succefully", True)
            if name:
                names.append(name)
                print(f"   {'✓' if ok else '✗'} {name}")
    except Exception as e:  # keep going with other chains
        print(f"   ! error: {e}")
    return names


def store_id_from_name(name):
    # PriceFull7290058140886-001-002-20261106-001017 -> 2  (chain-subchain-store-date)
    name = name or ""
    m = re.search(r"\d{13}-\d+-(\d+)-\d{8}", name) or re.search(r"\d{13}-(\d+)-\d{8,}", name)
    return int(m.group(1)) if m else None


async def download_chain(chain, max_stores):
    out = DUMPS / chain["id"]
    out.mkdir(parents=True, exist_ok=True)
    cls = ScraperFactory.get(chain["scraper"])

    def new():
        return cls(file_output=DiskFileOutput(storage_path=str(out)))

    print(f"== {chain['name']} ({chain['scraper']})")

    print(" stores file")
    await collect(new(), files_types=["STORE_FILE"], limit=1)

    store_ids = list(chain.get("store_ids") or [])
    if store_ids:
        for sid in store_ids:
            print(f" prices, store {sid}")
            await collect(new(), files_types=["PRICE_FULL_FILE"], store_id=int(sid), limit=3)
    else:
        print(f" prices, {max_stores} stores")
        # the newest files are often the same store several times, so take more and pick distinct stores
        names = await collect(new(), files_types=["PRICE_FULL_FILE"], limit=max_stores * 6)
        store_ids = []
        for s in map(store_id_from_name, names):
            if s is not None and s not in store_ids and len(store_ids) < max_stores:
                store_ids.append(s)
        print(f" chosen stores: {store_ids}")

    for sid in store_ids:
        print(f" promos, store {sid}")
        if sid > 0:
            await collect(new(), files_types=["PROMO_FULL_FILE"], store_id=int(sid), limit=3)
        else:
            await collect(new(), files_types=["PROMO_FULL_FILE"], limit=max_stores * 3)


async def main(only):
    max_stores = int(CONFIG.get("max_stores_per_chain", 3))
    for chain in CONFIG["chains"]:
        if only and chain["id"] not in only:
            continue
        if not only and not chain.get("enabled", True):
            continue
        await download_chain(chain, max_stores)


if __name__ == "__main__":
    asyncio.run(main(set(sys.argv[1:])))
