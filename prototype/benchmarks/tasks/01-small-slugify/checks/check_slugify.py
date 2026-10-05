import sys; sys.path.insert(0, ".")
from textkit import slugify
assert slugify("Hello, World!") == "hello-world"
assert slugify("  Đường   phố Hà Nội  ") == "duong-pho-ha-noi"
assert slugify("Crème brûlée -- 2024") == "creme-brulee-2024"
assert slugify("a" * 10 + " b", max_len=11) == "aaaaaaaaaa"
assert slugify("!!!") == "n-a" and slugify("") == "n-a"
print("ok")
