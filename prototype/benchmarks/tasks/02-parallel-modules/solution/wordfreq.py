import collections, re


def top_words(text, k):
    c = collections.Counter(re.findall(r"[\w']+", text.lower()))
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
