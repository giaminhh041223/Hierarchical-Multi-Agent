import math, re
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def price_after_discount(total, pct):
    if not 0 <= pct <= 100:
        raise ValueError("pct must be 0..100")
    return money(Decimal(total) * (100 - Decimal(pct)) / 100)


def shipping(subtotal, weight_kg):
    if not weight_kg > 0:
        raise ValueError("weight must be > 0")
    if Decimal(subtotal) >= 50:
        return money(0)
    extra = max(0, math.ceil(Decimal(weight_kg)) - 1)
    return money(Decimal("4.99") + Decimal("1.50") * extra)


def loyalty_points(paid):
    return max(0, int(Decimal(paid) // 10))


def split_payment(total, n):
    if n < 1:
        raise ValueError("n must be >= 1")
    cents = int(money(total) * 100)
    base, extra = divmod(cents, n)
    return [money(Decimal(base + (i < extra)) / 100) for i in range(n)]


def parse_coupon(code):
    if not isinstance(code, str):
        return None
    m = re.fullmatch(r"save([1-9]\d?)", code.strip(), re.I)
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 50 else None
