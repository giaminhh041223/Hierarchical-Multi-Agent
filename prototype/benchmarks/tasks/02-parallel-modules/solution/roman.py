import re

PAIRS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
         (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n):
    if not 1 <= n <= 3999:
        raise ValueError(n)
    out = ""
    for v, s in PAIRS:
        while n >= v:
            out, n = out + s, n - v
    return out


def from_roman(s):
    if not re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", s or "") or not s:
        raise ValueError(s)
    n, i = 0, 0
    for v, sym in PAIRS:
        while s.startswith(sym, i):
            n, i = n + v, i + len(sym)
    return n
