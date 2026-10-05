def line_amount(price, qty):
    return round(price * qty, 2)


def subtotal(items):
    return round(sum(line_amount(p, q) for _, p, q in items), 2)


def apply_discount(amount, pct):
    return amount * (1 - pct / 100)
