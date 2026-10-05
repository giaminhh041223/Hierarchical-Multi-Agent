import sys; sys.path.insert(0, ".")
from wordfreq import top_words
assert top_words("b a B a c don't don't don't", 3) == [("don't", 3), ("a", 2), ("b", 2)]
assert top_words("", 5) == []
print("ok")
