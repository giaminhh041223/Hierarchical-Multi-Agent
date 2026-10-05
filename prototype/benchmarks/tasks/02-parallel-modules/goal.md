Create four independent modules at the repository root, each with its own tests (test_<module>.py):
1. roman.py: to_roman(n) for 1..3999 and from_roman(s) that rejects non-canonical numerals ("IIII", "VX", "IM") with ValueError.
2. wordfreq.py: top_words(text, k) -> list of (word, count), case-insensitive, words = runs of letters/digits/apostrophes,
   ties broken alphabetically.
3. durations.py: parse_duration("1h30m15s") -> seconds (units d, h, m, s, any subset in that order; "90s" ok);
   ValueError on anything else, including "" and "1x".
4. csvstats.py: column_stats(path, column) -> {"count", "min", "max", "mean"} over the numeric values of a CSV column
   (header row; blank cells skipped; ValueError if the column is missing).
