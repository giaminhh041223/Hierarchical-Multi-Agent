import sys; sys.path.insert(0, ".")
from inifile import parse
text = "top = 1\n; comment\n# another\n\n[Server]\nHost = example.org \nport: 80\nurl = http://x/a=b\n[db]\nname=main\n[server]\nport = 8080\n"
assert parse(text) == {"": {"top": "1"}, "server": {"host": "example.org", "port": "8080", "url": "http://x/a=b"}, "db": {"name": "main"}}, parse(text)
assert parse("a: b = c")[""] == {"a": "b = c"}
try:
    parse("[a]\nx = 1\njust words\n")
    raise SystemExit("accepted a bad line")
except ValueError as e:
    assert "line 3" in str(e), e
print("ok")
