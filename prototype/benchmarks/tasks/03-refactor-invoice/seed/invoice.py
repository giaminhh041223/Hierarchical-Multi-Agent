"""One function does everything: prices, discount, tax and the text layout."""


def render_invoice(items, discount_pct=0, tax_pct=10):
    # items: [(name, unit_price, qty)]
    lines, subtotal = [], 0
    for name, price, qty in items:
        amount = round(price * qty, 2)
        subtotal += amount
        lines.append(f"{name:<20}{qty:>4} x {price:>8.2f} = {amount:>9.2f}")
    taxed = subtotal * (1 + tax_pct / 100)
    total = taxed * (1 - discount_pct / 100)  # BUG: the discount must apply before the tax
    lines.append("-" * 47)
    lines.append(f"{'Subtotal':<36}{subtotal:>11.2f}")
    lines.append(f"{'Discount ' + str(discount_pct) + '%':<36}{-subtotal * discount_pct / 100:>11.2f}")
    lines.append(f"{'Tax ' + str(tax_pct) + '%':<36}{taxed - subtotal:>11.2f}")
    lines.append(f"{'Total':<36}{round(total, 2):>11.2f}")
    return "\n".join(lines)
