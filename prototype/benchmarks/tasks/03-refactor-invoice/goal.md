Refactor invoice.py into three modules and fix its bug:
- pricing.py: line_amount(price, qty) (rounded to cents), subtotal(items), apply_discount(amount, pct);
- tax.py: tax_amount(amount, pct);
- render.py: render(items, discount_pct, tax_pct) -> the invoice text, same layout as today.
invoice.render_invoice(items, discount_pct=0, tax_pct=10) must keep working (it calls render.render).
The bug: the discount is applied after the tax; it must apply to the subtotal, and the tax to the discounted amount.
The "Tax" line shows that tax; "Total" = discounted subtotal + tax. Keep the layout otherwise identical. Add tests.
