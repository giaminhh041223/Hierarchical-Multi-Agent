from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity, self.data = capacity, OrderedDict()
        self.hits = self.misses = self.evictions = 0

    def get(self, key, default=None):
        if key in self.data:
            self.hits += 1
            self.data.move_to_end(key)
            return self.data[key]
        self.misses += 1
        return default

    def put(self, key, value):
        if key in self.data:
            self.data.move_to_end(key)
        self.data[key] = value
        if len(self.data) > self.capacity:
            self.data.popitem(last=False)
            self.evictions += 1

    def __len__(self):
        return len(self.data)

    def stats(self):
        return {"hits": self.hits, "misses": self.misses, "evictions": self.evictions}
