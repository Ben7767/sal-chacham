"""
בניית קובץ הנתונים לאתר מתוך קבצי ה-XML שהורדו.
Parses dumps/<chain_id>/*.xml (PriceFull, PromoFull, Stores) and writes
site/data/prices.json — one row per barcode with a price per chain.

Chain price = median of the regular price across the downloaded stores.
Promo = best promotion open to everyone (no club) that is valid today.
"""
import json
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DUMPS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dumps"
OUT = ROOT / "site" / "data" / "prices.json"
IL_TZ = timezone(timedelta(hours=2))


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def children(el):
    """dict of lower-case child tag -> text"""
    return {local(c.tag): (c.text or "").strip() for c in el}


def num(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def is_barcode(code):
    # internal chain codes (produce, weighed items) don't match between chains
    return code.isdigit() and len(code) >= 8 and not set(code) <= {"0"}


def file_kind(path):
    n = path.name.lower()
    if "promofull" in n:
        return "promo"
    if "pricefull" in n:
        return "price"
    if "store" in n:
        return "stores"
    return None


def iter_elements(path, names):
    for _, el in ET.iterparse(path, events=("end",)):
        if local(el.tag) in names:
            yield el
            el.clear()


def read_store_id(path):
    # PriceFull<chain>-<subchain>-<store>-<date>  (older: PriceFull<chain>-<store>-<date>)
    m = re.search(r"\d{13}-\d+-(\d+)-\d{8}", path.name) or re.search(r"\d{13}-(\d+)-\d{8,}", path.name)
    if m:
        return int(m.group(1))
    for _, el in ET.iterparse(path, events=("end",)):
        if local(el.tag) == "storeid":
            return int(num(el.text) or 0)
    return None


def parse_prices(path):
    items = {}
    for el in iter_elements(path, {"item", "product"}):
        d = children(el)
        code, price = d.get("itemcode", ""), num(d.get("itemprice"))
        if not is_barcode(code) or not price or price <= 0:
            continue
        items[code] = {
            "name": d.get("itemname") or d.get("manufactureritemdescription") or code,
            "brand": d.get("manufacturername", ""),
            "qty": d.get("quantity", ""),
            "unit": d.get("unitqty", "") or d.get("unitofmeasure", ""),
            "price": price,
        }
    return items


def parse_date(s):
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def parse_promos(path, today):
    """barcode -> list of (unit_price, min_qty, description, end_date)"""
    out = {}
    for el in iter_elements(path, {"promotion", "sale"}):
        d = children(el)
        start, end = parse_date(d.get("promotionstartdate")), parse_date(d.get("promotionenddate"))
        if (start and start > today) or (end and end < today):
            continue
        clubs = [(c.text or "").strip() for c in el.iter() if local(c.tag) == "clubid"]
        if clubs and not any(c == "" or re.match(r"0(\D|$)", c) for c in clubs):
            continue  # members-only promotion
        dp = num(d.get("discountedprice"))
        if not dp or dp <= 0:
            continue
        min_qty = num(d.get("minqty")) or 1
        codes = [(c.text or "").strip() for c in el.iter() if local(c.tag) == "itemcode"]
        for code in codes:
            if is_barcode(code):
                out.setdefault(code, []).append((dp, min_qty, d.get("promotiondescription", ""),
                                                 end.isoformat() if end else ""))
    return out


def promo_unit_price(promo, regular):
    dp, min_qty, desc, end = promo
    # some chains give the total for MinQty units ("2 ב-20"), others the unit price
    unit = dp / min_qty if (min_qty > 1 and dp > regular) else dp
    return round(unit, 2)


def build():
    today = datetime.now(IL_TZ).date()
    chains = [c for c in CONFIG["chains"] if (DUMPS / c["id"]).is_dir()]
    if not chains:
        sys.exit(f"no downloaded chains found in {DUMPS}")

    products = {}  # code -> info
    per_chain = []
    for c in chains:
        folder = DUMPS / c["id"]
        wanted = {int(s) for s in c.get("store_ids") or []}
        stores_prices, promos, store_ids = [], {}, []
        latest = {}  # (kind, store) -> newest file (names end with a timestamp)
        for path in sorted(folder.rglob("*.xml"), key=lambda p: p.name):
            kind = file_kind(path)
            if kind in ("price", "promo"):
                latest[(kind, read_store_id(path))] = path
        price_stores = sorted({sid for k, sid in latest if k == "price"})
        if wanted:
            price_stores = [s for s in price_stores if s in wanted]
        price_stores = price_stores[: max(len(wanted), int(CONFIG.get("max_stores_per_chain", 3)))]
        promo_debug = False
        for (kind, sid), path in sorted(latest.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
            if sid not in price_stores:
                continue
            try:
                if kind == "price":
                    stores_prices.append(parse_prices(path))
                    store_ids.append(sid)
                else:
                    found = parse_promos(path, today)
                    for code, lst in found.items():
                        promos.setdefault(code, []).extend(lst)
                    if not found and not promo_debug:
                        promo_debug = True
                        print(f"  no promos parsed from {path.name}; sample:")
                        print("  " + path.read_text(encoding="utf-8", errors="replace")[:1500].replace("\n", " "))
            except ET.ParseError as e:
                print(f"skip broken file {path.name}: {e}")

        prices = {}
        for sp in stores_prices:
            for code, info in sp.items():
                prices.setdefault(code, []).append(info["price"])
                products.setdefault(code, info)
        median = {code: round(statistics.median(v), 2) for code, v in prices.items()}
        best_promo = {}
        for code, lst in promos.items():
            if code not in median:
                continue
            reg = median[code]
            cands = [(promo_unit_price(p, reg), p) for p in lst]
            unit, p = min(cands, key=lambda x: x[0])
            if unit < reg:
                best_promo[code] = [unit, int(p[1]), p[2][:60], p[3]]
        per_chain.append((median, best_promo))
        print(f"{c['name']}: stores {store_ids}, {len(median)} products, {len(best_promo)} promos")

    rows = []
    for code, info in products.items():
        price_list = [m.get(code) for m, _ in per_chain]
        if sum(p is not None for p in price_list) < 2:
            continue  # only products we can actually compare
        promo_list = [bp.get(code) for _, bp in per_chain]
        rows.append([code, info["name"], info["brand"], info["qty"], info["unit"],
                     price_list, promo_list])
    rows.sort(key=lambda r: r[1])

    data = {
        "updated": datetime.now(IL_TZ).strftime("%Y-%m-%d %H:%M"),
        "demo": "sample" in str(DUMPS),
        "chains": [{"id": c["id"], "name": c["name"], "color": c.get("color", "#888")} for c in chains],
        "fields": ["barcode", "name", "brand", "qty", "unit", "prices", "promos"],
        "items": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(rows)} comparable products -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
