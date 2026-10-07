Create six independent modules at the repository root, each with its own tests (test_<module>.py). Standard library only.
1. semver.py: compare(a, b) -> -1, 0 or 1 by Semantic Versioning 2.0 precedence: MAJOR.MINOR.PATCH numerically; a version
   with a pre-release ("1.0.0-alpha.1") is lower than the same version without; pre-release identifiers compare left to
   right, numeric ones numerically and lower than alphanumeric ones, alphanumeric ones in ASCII order, and a longer list
   wins when all shared ones are equal; build metadata ("+build.5") is ignored. ValueError on an invalid version
   (missing parts, leading zeros in a numeric part, empty identifiers).
2. inifile.py: parse(text) -> {section: {key: value}}. Lines "[section]", "key = value" or "key: value" (split at the first
   "=" or ":"), blank lines, and comments starting with ";" or "#". Section and key names are lowercased, names and values
   stripped. Keys before any section go to section "". A repeated section merges into the first; a repeated key keeps the
   last value. Any other line raises ValueError whose message contains "line <n>" (1-based).
3. lru.py: class LRUCache(capacity) with get(key, default=None), put(key, value), len(cache) and stats() ->
   {"hits": h, "misses": m, "evictions": e}. get counts a hit or a miss and makes the key most recently used; put of an
   existing key updates it and makes it most recently used; put beyond capacity evicts the least recently used key.
   capacity < 1 raises ValueError.
4. luhn.py: is_valid(number) -> bool: spaces ignored, any other non-digit or fewer than 2 digits -> False, else the Luhn
   checksum. check_digit(partial) -> the digit (a str) that makes partial valid when appended. mask(number) -> every digit
   except the last four replaced by "*", spaces kept.
5. intervals.py: merge(intervals) -> sorted list of merged (start, end) tuples; overlapping or touching intervals merge
   ((1, 3) and (3, 5) -> (1, 5)). total_length(intervals) -> the length covered (overlaps counted once). ValueError if an
   interval has start > end.
6. cron.py: matches(expr, dt) -> bool for a 5-field cron expression "minute hour day-of-month month day-of-week" and a
   datetime. Each field: "*", a number, a range "a-b", a list "a,b,c" of numbers or ranges, or a step "*/n" or "a-b/n".
   Day-of-week 0-6 with 0 = Sunday. When both day-of-month and day-of-week are restricted (not "*"), the day matches if
   either one does. ValueError on a malformed expression or a value out of range.
