"""Text helpers."""
import re, unicodedata


def slugify(text, max_len=None):
    s = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    s = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in s if not unicodedata.combining(c)).lower()).strip("-")
    if max_len is not None:
        s = s[:max_len].rstrip("-")
    return s or "n-a"
