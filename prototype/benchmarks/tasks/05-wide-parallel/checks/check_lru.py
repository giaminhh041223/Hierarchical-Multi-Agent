import sys; sys.path.insert(0, ".")
from lru import LRUCache
c = LRUCache(2)
c.put("a", 1); c.put("b", 2)
assert c.get("a") == 1  # a is now most recent
c.put("c", 3)  # evicts b
assert c.get("b") is None and c.get("b", "x") == "x" and len(c) == 2
c.put("a", 10)  # update refreshes a
c.put("d", 4)  # evicts c
assert c.get("c") is None and c.get("a") == 10 and c.get("d") == 4
assert c.stats() == {"hits": 3, "misses": 3, "evictions": 2}, c.stats()
try:
    LRUCache(0)
    raise SystemExit("accepted capacity 0")
except ValueError:
    pass
print("ok")
