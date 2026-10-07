def _sum(digits):
    total = 0
    for i, d in enumerate(reversed(digits)):
        d = int(d)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total


def is_valid(number):
    digits = number.replace(" ", "")
    if len(digits) < 2 or not digits.isascii() or not digits.isdigit():
        return False
    return _sum(digits) % 10 == 0


def check_digit(partial):
    digits = partial.replace(" ", "")
    return str((10 - _sum(digits + "0") % 10) % 10)


def mask(number):
    total = sum(c.isdigit() for c in number)
    out, seen = [], 0
    for c in number:
        if c.isdigit():
            seen += 1
            out.append(c if seen > total - 4 else "*")
        else:
            out.append(c)
    return "".join(out)
