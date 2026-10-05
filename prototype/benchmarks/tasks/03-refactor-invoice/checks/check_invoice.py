import sys; sys.path.insert(0, ".")
import invoice, pricing, render, tax
items = [("Widget", 19.99, 3), ("Gadget", 5.5, 10)]
assert pricing.line_amount(19.99, 3) == 59.97 and pricing.subtotal(items) == 114.97
assert abs(pricing.apply_discount(100, 15) - 85) < 1e-9 and abs(tax.tax_amount(85, 10) - 8.5) < 1e-9
expected = "\n".join([
    "Widget                 3 x    19.99 =     59.97",
    "Gadget                10 x     5.50 =     55.00",
    "-" * 47,
    "Subtotal                                 114.97",
    "Discount 10%                             -11.50",
    "Tax 8%                                     8.28",
    "Total                                    111.75"])
got = invoice.render_invoice(items, discount_pct=10, tax_pct=8)
assert got == expected, "\n" + got
assert render.render(items, 10, 8) == expected
assert invoice.render_invoice([("A", 10, 1)]).splitlines()[-1].endswith("11.00")
print("ok")
