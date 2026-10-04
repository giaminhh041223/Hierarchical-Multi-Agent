# Bàn giao: tiếp tục trên Claude Code cloud (2026-10-04)

Phiên local hết usage giữa chừng. File này đủ để phiên cloud làm tiếp mà không cần lịch sử hội thoại.
- Đọc cùng `CLAUDE.md` (quy tắc, giới hạn của cloud) và `prototype/PLAN.md`.
- Xong hết các việc ở đây thì xoá file này.

## 1. Hiện trạng

| Nhánh | Nội dung |
|---|---|
| `orchestra-prototype` | <ul><li>P1 xong.</li><li>P2 đã có sơ đồ DAG, sửa plan bằng kéo-thả, MCP server, embeddings cho knowledge graph.</li><li>Worker chạy từ xa: mới có `_git(..., text=False)` trong `engine.py` (đọc byte, để chở patch nhị phân).</li><li>25 test pass.</li></ul> |
| `orchestra-uiux` | Thiết kế lại web UI theo `docs/UIUX.md`, chưa merge. <ul><li>Pha 1 và 2 đã review.</li><li>`/api/state` thêm `workers`, `budget`, `attempts`; `/api/models` thêm `info`.</li><li>Pha 3 do Gemini viết, **chưa review**.</li></ul> |

Người dùng nhờ Gemini (agy, `gemini-3.8-flash-high`) làm UI. agy chỉ có trên máy người dùng, nên trên cloud Claude tự review và làm tiếp phần UI.

## 2. Thứ tự việc

1. Worker chạy từ xa (§3): có test, commit riêng trên `orchestra-prototype`.
2. Review Pha 3 UI trên `orchestra-uiux` (§4), sửa lỗi, commit.
3. Pha 4 UI: `docs/UIUX.md` §12. Ảnh chụp cho README cần trình duyệt; không có thì để người dùng làm ở local.
4. Merge `orchestra-uiux` vào `orchestra-prototype`. Xung đột dự kiến:
   - `server.py`: route lease và cách đọc body ở §3.3, so với `api_state` / `api_models` của nhánh UI. Giữ cả hai.
   - `tests/test_e2e.py`, docs, số test trong `CLAUDE.md`.
5. Cập nhật tài liệu:
   - `PLAN.md` §0, §10, §13, §15, §16;
   - `README.md`, `CLAUDE.md`, `docs/UIUX.md` §12.
6. Quét secret, rồi hỏi người dùng trước khi push.

## 3. Worker chạy từ xa: thiết kế đã chốt

Mục tiêu: một máy khác (có CLI và login riêng) làm worker. Engine, scope, verify và merge vẫn ở máy chính.

Luồng:
1. Team khai báo worker `{"agent": "remote", "model": "codex:gpt-5.5"}`. Model ghi agent thật và model, tách ở dấu `:` đầu tiên.
2. Engine gọi profile `remote` như mọi agent CLI khác, không phải sửa engine:
   - lệnh: `python -m orch remote proxy <agent>:<model> --mode rw|ro --schema <file>`;
   - prompt qua stdin;
   - kết quả ra stdout, dạng JSON của agy.
3. Proxy chụp worktree thành một commit không cha, đóng `git bundle`, ghi lease vào bảng `leases`, rồi chờ.
4. Runner chạy ở máy kia: `python -m orch remote run --url http://127.0.0.1:<port>`, qua đường hầm `ssh -R`. Runner:
   - nhận lease qua server của web UI;
   - dựng repo tạm từ bundle;
   - chạy agent thật bằng `agents.run_agent`, gửi heartbeat trong lúc chạy;
   - cuối cùng gửi patch nhị phân và kết quả.
5. Proxy áp patch vào worktree bằng `git apply` rồi in JSON. Engine verify và gộp như với worker local.

### 3.1 Catalog, account, schema

`catalog/agents.json`, profile mới:
```json
"remote": {"name": "Remote runner (python -m orch remote run on another machine)", "bin": "python", "verified": false, "hidden": true, "remote": true,
  "mode": {"rw": "rw", "ro": "ro"}, "run": ["-m", "orch", "remote", "proxy", "{model}", "--mode", "{mode}", "--schema", "{schema}"],
  "prompt": "stdin", "parse": "agy"}
```
- Không có `resume`, không có `mcp`: worker từ xa không có MCP hay knowledge graph.
- Lời gọi không có schema thì `fill` tự bỏ `--schema {schema}`.
- Engine truyền schema dạng tên hợp đồng (`schema=contract_name`), `fill` đổi thành đường dẫn file. Proxy lưu `Path(schema).stem`; runner truyền lại tên đó cho `run_agent`.

`agents.account()`, thêm trước nhánh router:
```python
    if a.get("remote"):  # ponytail: every runner of one CLI counts as one account
        return f"{aid}/{(model or '').split(':', 1)[0]}"
```

`core.py`, thêm vào SCHEMA sau `vectors`:
```sql
CREATE TABLE IF NOT EXISTS leases(id TEXT PRIMARY KEY, task TEXT, agent TEXT, model TEXT, prompt TEXT, schema TEXT, readonly INT,
  base TEXT, pid INT, pid_ctime TEXT, stale REAL, status TEXT DEFAULT 'open', runner TEXT, beat REAL, result TEXT, created REAL);
```

### 3.2 `orch/remote.py` (module mới)

Import:
- stdlib: base64, json, os, re, secrets, socket, sys, tempfile, threading, time, urllib.error, urllib.request, `Path`;
- trong package: `from . import agents`, `from .core import HOME, Workspace, vault`, `from .engine import _git, ensure_excluded, git_ok`.

Helper:
- `_env(name, default)`: `float(os.environ.get(name) or default)`.
- `_files(ws, lid)`: `[ws.dir / "leases" / f"{lid}.{x}" for x in ("bundle", "patch", "index")]`.
- `_raw(cwd, *args, env=None)`: gọi `_git(..., text=False)`, exit khác 0 thì `RuntimeError(stderr)`, trả về bytes.
- `drop(ws, lid)`: xoá dòng lease và ba file.
- `alive(L)`: `agents.proc_ctime(L["pid"]) == L["pid_ctime"]`.
- `sweep(ws)`: drop các lease có proxy đã chết. Engine kill proxy thì `finally` của proxy không chạy.

`snapshot(cwd, bundle, lid)` chụp cả thay đổi chưa commit mà không đụng index thật:
```python
    index = ...  # file .index của lease
    env = {"GIT_INDEX_FILE": str(index)}
    _raw(cwd, "read-tree", "HEAD", env=env)  # keeps tracked-but-ignored files
    _raw(cwd, "add", "-A", env=env)
    if (Path(cwd) / ".agents" / "skills").is_dir():
        _raw(cwd, "add", "-f", "--", ".agents/skills", env=env)  # installed orch-* skills sit in info/exclude
    tree = _raw(cwd, "write-tree", env=env).decode().strip()
    sha = _raw(cwd, "commit-tree", tree, "-m", f"orch lease {lid}").decode().strip()  # no parent: no history leaves
    ref = f"refs/orch/lease-{lid}"
    _raw(cwd, "update-ref", ref, sha)  # `git bundle create f <sha>` says "Refusing to create empty bundle"
    try:
        _raw(cwd, "bundle", "create", str(bundle), ref)
    finally:
        _raw(cwd, "update-ref", "-d", ref)
        index.unlink(missing_ok=True)
    return sha
```

`proxy(spec, mode, schema)` chạy trong worktree; engine đặt sẵn `ORCH_WS`.
1. Chuẩn bị:
   - Đọc prompt từ stdin.
   - `ws = Workspace(os.environ.get("ORCH_WS") or sys.exit("remote proxy: ORCH_WS is not set (the engine sets it)"))`, rồi `ws.quiet = True`.
   - `lid = secrets.token_hex(6)`; `agent, _, model = spec.partition(":")`.
   - Agent không có trong catalog, hoặc thiếu model: lỗi `remote model ... must be <agent>:<model>`.
2. Tạo lease:
   - `sweep`, rồi tạo thư mục `ws.dir/leases`.
   - `base = snapshot(...)` nếu `git_ok(cwd, "rev-parse", "--verify", "HEAD")`, không thì `None`.
   - Task lấy từ header `ORCH-CALL role=X task=Y` trong prompt.
   - `stale = _env("ORCH_REMOTE_STALE", 60)`, `wait = _env("ORCH_REMOTE_WAIT", 600)`.
   - INSERT lease với:
     - `schema = Path(schema).stem`, `readonly = mode == "ro"`;
     - pid và `proc_ctime` của `os.getpid()`;
     - `stale`: lưu vào lease để runner beat theo cùng giá trị.
3. Mỗi giây đọc lại lease:
   - `done`: thoát vòng.
   - Dòng mất: lỗi `the lease was removed`.
   - Còn `open` quá `wait`: lỗi `no remote runner took this attempt within {wait}s: start one on the other machine with python -m orch remote run --url <orch ui address>`.
   - `claimed` mà `beat` cũ hơn `stale`: lỗi `remote runner {runner} stopped responding (no heartbeat for {stale}s)`.
4. Kết quả ok, không phải ro, patch khác rỗng: chạy `_git(cwd, "apply", patch)`.
   - Không dùng `--index`, để autocrlf tự xử lý.
   - Lỗi thì báo `the remote patch does not apply here: ...`.
5. In JSON: `{"status": "SUCCESS"|"ERROR", "response": text, "conversation_id": session, "usage": {"input_tokens", "output_tokens"}, "error": error}`.
   - `RuntimeError` gom vào `error`.
   - `finally: drop(ws, lid)`; lúc nào cũng in JSON.
   - Lỗi qua `classify` thành `error`, nên `route` cho engine thử lại một lần.

Handler phía server, cùng chữ ký với route của web UI `(ws, b, q=None)`:
- `claim`:
  - `sweep`; `have = b["agents"]`; `runner = str(b["runner"])[:64]`.
  - Trong `ws.tx()`: lấy lease `open` cũ nhất có `agent IN have`, chuyển sang `claimed`, ghi `runner` và `beat=now`.
  - Ghi event `ws.event("remote", f"{runner} took the attempt ({agent}/{model})", task, "remote")`.
  - Trả `{"lease": {id, agent, model, prompt, schema, readonly, base, stale}, "bundle": <base64> | None}`, không có lease thì `{"lease": None}`.
- `beat`:
  - `claimed` mà proxy đã chết: drop, trả `{"cancel": True}`.
  - `claimed`: cập nhật `beat`, trả `{"cancel": False}`.
  - Còn lại: `{"cancel": True}`.
- `done`:
  - id phải khớp `[0-9a-f]{12}`.
  - `base64.b64decode(patch, validate=True)`; khác rỗng thì ghi file patch.
  - `result` gồm ok, text, session, tokens_in, tokens_out, error, đã ép kiểu.
  - CAS từ `claimed` sang `done`. Không được thì xoá file patch và `ValueError("this lease is gone: the engine gave up on it (or stopped)")`.
  - Trả `{"ok": "result recorded"}`.

`run(url, name=None, have=None, once=False)` là vòng lặp của runner.
1. Chuẩn bị:
   - Token lấy từ env `ORCH_REMOTE_TOKEN` hoặc vault của máy runner. Thiếu thì `SystemExit` kèm hướng dẫn.
   - `name` mặc định là `socket.gethostname()`.
   - `have` mặc định là các agent không ẩn đã cài. Id không có trong catalog thì `SystemExit`; profile ẩn như `mock` vẫn hợp lệ.
   - `OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))`, để biến `http_proxy` không làm lộ token.
   - POST JSON với header `X-Orch-Token`, timeout 120.
   - In `remote runner {name}: serving {have} for {url}`.
2. Lặp: gọi claim.
   - `HTTPError`: `SystemExit` với thông báo của server.
   - `OSError`: in một lần rồi thử lại.
   - Có lease: `serve_lease`. Với `once` thì return sau lease đó; không thì ngủ 2 giây rồi lặp.

`serve_lease(got, name, post)`:
1. `state = {"kill": None, "stop": False}`. `on_start` của `run_agent` lưu hàm kill; nếu đã stop thì kill ngay.
2. Thread heartbeat, mỗi `stale / 6` giây:
   - nhận `cancel`: stop và kill;
   - không gọi được server liên tục từ `stale` giây trở lên: cũng stop.
3. Trong `tempfile.TemporaryDirectory(prefix="orch-remote-", ignore_cleanup_errors=True)`: ghi bundle, `init -q`, `bundle unbundle`, `checkout -q --detach <base>`, rồi `ensure_excluded(repo)`.
4. Chạy `run_agent(agent, model, prompt + <note của agent thật trong catalog>, repo, HOME / "remote" / lid, schema, readonly, on_start=..., timeout=86400)`.
   - Engine quyết định hết giờ: nó kill proxy, `beat` trả cancel.
5. Lấy patch bằng `add -A` rồi `diff --cached --binary <base>` (bytes). Chỉ lấy khi ok, không ro, có base và chưa stop.
6. Đã stop thì không gửi gì, in `cancelled`. Không thì POST `lease/done` và in một dòng kết quả.

### 3.3 `server.py`

- `MAX_PATCH = 50_000_000`; `from . import remote`.
- `POST` thêm `"lease": remote.claim, "lease/beat": remote.beat, "lease/done": remote.done`.
- `make_server`:
  - `rt = os.environ.get("ORCH_REMOTE_TOKEN") or vault().get("ORCH_REMOTE_TOKEN")`;
  - `srv.remote_token = rt if rt and len(rt) >= 16 else None`.
- `serve()` in `remote runners: on`, hoặc cảnh báo token quá ngắn. Không bao giờ in token.
- `Handler.serve` viết lại theo thứ tự sau:
```python
        lease = url.path.startswith("/api/lease")
        key, limit = (srv.remote_token, MAX_PATCH) if lease else (srv.token, MAX_BODY)
        ok_token = bool(key) and hmac.compare_digest(self.headers.get("X-Orch-Token", "").encode(), key.encode())
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        # read the body before any reply: on Windows a reply sent over an unread body becomes a connection reset
        # (WinError 10053, the cause of the occasional test_ui_server_security failure)
        raw = self.rfile.read(n) if routes is POST and 0 < n <= (limit if ok_token else MAX_BODY) else b""
```
  Sau đó lần lượt:
  1. Kiểm Host.
  2. Trang `/`.
  3. Origin và `ok_token`, sai thì 403. Với route lease, thông báo là `forbidden: remote runners need ORCH_REMOTE_TOKEN (16+ characters, the same value on both machines)`.
  4. Route không có: 404.
  5. `not 0 <= n <= limit` hoặc Content-Type không phải JSON: 413.
  6. `json.loads(raw or b"{}")`.
- Token của UI không mở được `/api/lease*`; token remote không mở được route khác.

### 3.4 `__main__.py`

`cmd_remote(a)`:
- `from . import remote`.
- Với `proxy`: `remote.proxy(a.spec, a.mode, a.schema)`.
- Còn lại: `remote.run(a.url, a.name, a.agents.split(",") if a.agents else None, a.once)`.

Subparser `remote`:
- `action`: choices `run`, `proxy`; `spec`: nargs="?".
- `--url` (mặc định `http://127.0.0.1:8765`), `--name`, `--agents` (cách nhau bằng dấu phẩy), `--once`.
- `--mode` (mặc định `rw`) và `--schema`, cả hai `help=argparse.SUPPRESS`.

### 3.5 Test `test_remote_worker` (thành 26 test)

- Helper `ui_server`: thêm `call.base = base` trước `yield`.
- Token sinh ngay trong test, không ghi ra chỗ khác.

```python
def test_remote_worker():
    import secrets
    tok = secrets.token_urlsafe(24)
    sc = {"plan": [task("T1", "far", ["far.txt"], [["python", "-c", "assert open('far.txt').read().strip() == 'far'"]])],
          "steps": {"worker:T1": [{"write": {"far.txt": "far\n"}}]}}
    r = Repo(sc, workers={"far": {"agent": "remote", "model": "mock:mock-fast", "max": 1}})
    with unittest.mock.patch.dict(os.environ, ORCH_REMOTE_TOKEN=tok), ui_server(r.repo) as call:
        out = open(r.tmp / "engine.out", "w")  # a file, not a pipe: a full pipe hangs the child on Windows
        eng = subprocess.Popen([sys.executable, "-m", "orch", "--ws", str(r.repo), "run", "demo goal", "--yes", "--exit-on-wait"],
                               cwd=ROOT, env={**r.env, "ORCH_REMOTE_STALE": "2", "ORCH_REMOTE_WAIT": "60"},
                               stdout=out, stderr=subprocess.STDOUT)
        ...
```
Phần còn lại của test:
1. Runner "ma" nhận lease rồi im lặng:
   - lặp `call("/api/lease", {"agents": ["mock"], "runner": "ghost"}, token=tok)` tới khi có lease;
   - kiểm `agent == "mock"`, `model == "mock-fast"`, prompt bắt đầu bằng `ORCH-CALL role=worker task=T1`, có bundle;
   - chờ dòng lease biến mất (proxy bỏ cuộc sau 2 giây);
   - kiểm `beat` trả `{"cancel": true}` và `done` trả 400 có chữ `gone`.
2. Bảo mật: token UI gọi `/api/lease` bị 403; token remote gọi `/api/state` bị 403.
3. Runner thật, phải trả 0:
   ```python
   subprocess.run([sys.executable, "-m", "orch", "remote", "run", "--url", call.base, "--name", "box1", "--agents", "mock", "--once"],
                  cwd=ROOT, env={**r.env, "ORCH_REMOTE_TOKEN": tok, "ORCH_HOME": str(r.tmp / "remote-home")}, timeout=120)
   ```
4. `eng.wait(...) == 0`.

Kiểm cuối:
- status là `{PLAN, T1, REVIEW: done}`;
- `r.show("far.txt").strip() == "far"`;
- `outcomes("T1") == ["error", "integrated"]`, lỗi lần đầu chứa `remote runner ghost stopped responding`;
- có event chứa `box1 took`;
- bảng `leases` rỗng, thư mục `.orch/leases` không còn file.

### 3.6 Tài liệu

`README.md`: thêm mục "Worker chạy từ xa" cạnh mục "MCP server", gồm:
- Đường hầm `ssh -R <port>:127.0.0.1:<port> user@máy-kia`. Hai đầu phải cùng port, vì server kiểm Host.
- Token:
  - sinh bằng `python -c "import secrets; print(secrets.token_urlsafe(24))"`;
  - hai máy dùng cùng giá trị, đặt qua env hoặc `vault set ORCH_REMOTE_TOKEN`.
- Ví dụ `team.json`.
- Những điều cần biết:
  - patch vẫn qua scope và verify ở máy chính;
  - snapshot không chở lịch sử git;
  - worker từ xa không có MCP hay knowledge graph;
  - log của runner ở `~/.orchestra/remote/<id>`.
- Biến môi trường: `ORCH_REMOTE_TOKEN`, `ORCH_REMOTE_STALE` (60), `ORCH_REMOTE_WAIT` (600).
- Mục bảo mật: ai có token thì đọc được mã nguồn và prompt.

`PLAN.md`:
- Bỏ dòng "Cố ý chưa làm | Worker chạy từ xa." ở §0.
- Sửa dòng về worker chạy từ xa ở §16.
- Bổ sung §10, §13, §15.

`CLAUDE.md`: đổi thành 26 test, thêm `remote.py` vào bản đồ module, sửa dòng P2 cuối file.

### 3.7 Bẫy git đã kiểm

- `git bundle create f <sha>` báo "Refusing to create empty bundle". Phải tạo ref tạm `refs/orch/lease-<id>`, bundle xong thì xoá.
- Repo mới nhận bundle bằng `git init`, `git bundle unbundle f`, rồi `git checkout -q --detach <sha>`.
- Hàm `git()` của engine decode và strip output, nên làm hỏng patch nhị phân. Dùng `_git(..., text=False)`.

## 4. Review Pha 3 UI (`orchestra-uiux`)

Gemini báo đã làm:
- Từ điển `VI` và hàm `t()`; nút EN/VI lưu ở `localStorage["orch.lang"]`, mặc định `vi`.
- Form Team cho lead, reviewer, skill architect và worker; sửa JSON thành chế độ nâng cao.
- Badge đăng nhập và probe cho tab Agent.
- Vault có hướng dẫn.
- Bảng Model 9 cột, sắp xếp được, có `aria-sort`.
- Trạng thái trống có nút hành động.

Đã kiểm ở local:
- Không có innerHTML, outerHTML, insertAdjacentHTML, eval, hay URL ngoài (trừ namespace SVG).
- Đúng một thẻ `<style>` và một thẻ `<script>`; file 89 856 byte.
- Kết quả bộ test ghi trong message commit của Pha 3.

Còn phải làm:
- Đọc diff (khoảng +830/−400 dòng):
  - mọi text đi qua `h()` hoặc `svg()`;
  - form Team giữ đúng schema mà `save_team` kiểm;
  - không tự POST khi người dùng chưa bấm.
- Chạy test lọc theo `ui`, `security`, `plan_edit`, rồi cả bộ test.
- QA trên trình duyệt: `python -m orch --ws <repo thử> ui --port <port> --no-browser`, nếu phiên có trình duyệt. Không có thì nhờ người dùng QA ở local. Cần xem:
  - sáng/tối, màn 375px;
  - chuyển VI/EN;
  - tạo team không gõ JSON;
  - sắp xếp bảng Model;
  - dùng hoàn toàn bằng bàn phím.
- Cập nhật `docs/UIUX.md` §12.

## 5. Quy tắc riêng của đợt này

Bổ sung cho `CLAUDE.md`:
- **Bí mật:**
  - Repo **public**. Không commit token, file auth, `.orch/`, `.orchestra/`, log.
  - Không ghi email của người dùng hay chi tiết bảo mật máy họ (cấu hình 9router) vào repo.
  - Token test (`ORCH_REMOTE_TOKEN`, key embeddings giả) chỉ nằm trong test.
- **Cấu hình và mạng:**
  - Không ghi config global của agent CLI; MCP truyền theo từng lần gọi.
  - Runner chỉ nối qua 127.0.0.1 hoặc đường hầm SSH. Không đổi firewall.
  - Gửi fact ra endpoint embeddings phải do người dùng bật (`"embeddings"` trong `team.json`).
- **Git:**
  - Mỗi tính năng một commit.
  - Không dùng `git stash` trần.
  - Chỉ push khi người dùng bảo.
- **Phong cách:**
  - Chỉ dùng thư viện chuẩn, code tối giản.
  - Mỗi tính năng một check trong `tests/test_e2e.py`.
  - Docs viết bằng tiếng Việt.
