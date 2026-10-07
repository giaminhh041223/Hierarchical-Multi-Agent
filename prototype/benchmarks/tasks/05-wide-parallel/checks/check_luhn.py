import sys; sys.path.insert(0, ".")
from luhn import check_digit, is_valid, mask
assert is_valid("4539 3195 0343 6467") and is_valid("79927398713") and not is_valid("79927398710")
assert not is_valid("0") and not is_valid("4539-3195") and not is_valid("") and is_valid("00") and not is_valid("12a4")
assert check_digit("7992739871") == "3" and check_digit("453931950343646") == "7"
assert mask("4539 3195 0343 6467") == "**** **** **** 6467" and mask("1234") == "1234" and mask("12345") == "*2345"
print("ok")
