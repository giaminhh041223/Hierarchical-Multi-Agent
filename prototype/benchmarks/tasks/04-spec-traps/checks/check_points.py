import sys; sys.path.insert(0, ".")
from decimal import Decimal as D
from checkout import loyalty_points
r = loyalty_points(D("39.99"))
assert r == 3 and type(r) is int, r
assert loyalty_points(D("9.99")) == 0 and loyalty_points(D("10.00")) == 1 and loyalty_points(D("0")) == 0
assert loyalty_points(D("-5.00")) == 0
print("ok")
