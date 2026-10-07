import sys; sys.path.insert(0, ".")
from decimal import Decimal as D
from checkout import split_payment
assert split_payment(D("10.00"), 3) == [D("3.34"), D("3.33"), D("3.33")]
assert split_payment(D("0.05"), 2) == [D("0.03"), D("0.02")]
assert split_payment(D("7.00"), 1) == [D("7.00")]
assert sum(split_payment(D("100.01"), 7)) == D("100.01")
try:
    split_payment(D("1.00"), 0)
    raise SystemExit("accepted n 0")
except ValueError:
    pass
print("ok")
