In textkit.py, implement slugify(text, max_len=None) -> str:
- lower-case; Vietnamese and other accented letters lose their accents ("Đường phố" -> "duong-pho");
- every run of characters that are not a-z or 0-9 becomes one "-"; no "-" at either end;
- max_len cuts the slug to at most max_len characters, never ending in "-";
- an empty result returns "n-a".
Add tests for it in test_textkit.py.
