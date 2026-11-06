"""
יוצר קבצי XML לדוגמה במבנה של הרשתות, לבדיקת build_data.py בלי אינטרנט.
The prices are made up — for testing only.
Usage: python tests/make_sample.py && python scripts/build_data.py tests/sample_dumps
"""
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "sample_dumps"
CHAINS = {"rami": "7290058140886", "osher": "7290103152017", "yoh": "7290803800003"}
PRODUCTS = [
    ("7290004131074", "חלב טרי 3% בקרטון", "תנובה", "1", "ליטר", 7.1),
    ("7290000042435", "קוטג' 5%", "תנובה", "250", "גרם", 6.4),
    ("7290011194246", "פסטה ספגטי", "אסם", "500", "גרם", 5.9),
    ("7290000068428", "במבה", "אסם", "80", "גרם", 5.2),
    ("7290000171685", "קפה נמס", "עלית", "200", "גרם", 29.9),
    ("7290000066318", "שמן קנולה", "שמן", "1", "ליטר", 11.9),
    ("7290102398065", "אורז פרסי", "סוגת", "1", "ק\"ג", 9.9),
    ("7290000072753", "קטשופ", "אסם", "750", "גרם", 12.9),
    ("7290011498894", "נייר טואלט 32 גלילים", "לילי", "32", "יחידה", 49.9),
    ("7290000137308", "טונה בשמן", "סטארקיסט", "4", "יחידה", 26.9),
]

PRICE_XML = """<?xml version="1.0" encoding="utf-8"?>
<Root><ChainId>{chain}</ChainId><StoreId>{store}</StoreId><Items Count="{n}">{items}</Items></Root>"""
ITEM = ("<Item><ItemCode>{code}</ItemCode><ItemType>1</ItemType><ItemName>{name}</ItemName>"
        "<ManufacturerName>{brand}</ManufacturerName><UnitQty>{unit}</UnitQty><Quantity>{qty}</Quantity>"
        "<ItemPrice>{price:.2f}</ItemPrice></Item>")
PROMO_XML = """<?xml version="1.0" encoding="utf-8"?>
<Root><ChainId>{chain}</ChainId><StoreId>{store}</StoreId><Promotions>
<Promotion><PromotionId>1</PromotionId><PromotionDescription>2 ב-{total}</PromotionDescription>
<PromotionStartDate>2020-01-01</PromotionStartDate><PromotionEndDate>2099-12-31</PromotionEndDate>
<MinQty>2</MinQty><DiscountedPrice>{total}</DiscountedPrice><Clubs><ClubId>0</ClubId></Clubs>
<PromotionItems><Item><ItemCode>{code}</ItemCode></Item></PromotionItems></Promotion>
<Promotion><PromotionId>2</PromotionId><PromotionDescription>מועדון בלבד</PromotionDescription>
<PromotionStartDate>2020-01-01</PromotionStartDate><PromotionEndDate>2099-12-31</PromotionEndDate>
<MinQty>1</MinQty><DiscountedPrice>1.00</DiscountedPrice><Clubs><ClubId>3</ClubId></Clubs>
<PromotionItems><Item><ItemCode>{code}</ItemCode></Item></PromotionItems></Promotion>
</Promotions></Root>"""

random.seed(7)
for cid, chain in CHAINS.items():
    folder = OUT / cid
    folder.mkdir(parents=True, exist_ok=True)
    for store in (1, 2):
        items = "".join(ITEM.format(code=c, name=n, brand=b, qty=q, unit=u,
                                    price=p * random.uniform(0.9, 1.15))
                        for c, n, b, q, u, p in PRODUCTS if not (cid == "yoh" and c.endswith("8894")))
        items += ITEM.format(code="1234", name="עגבניות (קוד פנימי)", brand="", qty="1", unit="ק\"ג", price=6.9)
        (folder / f"PriceFull{chain}-{store:03d}-202611060300.xml").write_text(
            PRICE_XML.format(chain=chain, store=store, n=len(PRODUCTS), items=items), encoding="utf-8")
        code = random.choice(PRODUCTS)[0]
        reg = [p for c, *_, p in PRODUCTS if c == code][0]
        (folder / f"PromoFull{chain}-{store:03d}-202611060300.xml").write_text(
            PROMO_XML.format(chain=chain, store=store, code=code, total=f"{reg * 1.6:.2f}"), encoding="utf-8")
print("sample dumps ->", OUT)
