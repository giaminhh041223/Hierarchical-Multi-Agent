from pricing import apply_discount, line_amount, subtotal
from tax import tax_amount


def render(items, discount_pct, tax_pct):
    lines = [f"{n:<20}{q:>4} x {p:>8.2f} = {line_amount(p, q):>9.2f}" for n, p, q in items]
    sub = subtotal(items)
    discounted = apply_discount(sub, discount_pct)
    t = tax_amount(discounted, tax_pct)
    lines += ["-" * 47, f"{'Subtotal':<36}{sub:>11.2f}", f"{'Discount ' + str(discount_pct) + '%':<36}{discounted - sub:>11.2f}",
              f"{'Tax ' + str(tax_pct) + '%':<36}{t:>11.2f}", f"{'Total':<36}{round(discounted + t, 2):>11.2f}"]
    return "\n".join(lines)
