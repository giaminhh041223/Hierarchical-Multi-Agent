"""Kept for callers: the work happens in pricing, tax and render."""
import render


def render_invoice(items, discount_pct=0, tax_pct=10):
    return render.render(items, discount_pct, tax_pct)
