import sys; sys.path.insert(0, ".")
from intervals import merge, total_length
assert merge([(5, 8), (1, 3), (3, 4), (10, 12), (11, 11)]) == [(1, 4), (5, 8), (10, 12)]
assert merge([]) == [] and total_length([(1, 5), (2, 3), (7, 9)]) == 6 and total_length([(0, 0)]) == 0
try:
    merge([(3, 1)])
    raise SystemExit("accepted start > end")
except ValueError:
    pass
print("ok")
