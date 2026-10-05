# CLAUDE.md

Bối cảnh cho Claude Code (local hoặc cloud) khi làm việc trong repo này. Người dùng nói tiếng Việt: trả lời và viết tài liệu bằng tiếng Việt.

## Repo gồm gì

- `prototype/`: **code đang phát triển**. Hoatau (tên cũ Orchestra; license Apache-2.0) là môi trường local, lấy cảm hứng từ n8n, điều phối nhiều AI coding agent CLI (codex, agy/Antigravity, opencode, claude, gemini …):
  - lead và reviewer lập plan;
  - worker chạy song song, mỗi worker một git worktree;
  - engine verify rồi gộp kết quả;
  - việc vượt quyền lead thì hỏi người dùng.

  Đọc trước khi sửa: `prototype/README.md` (cách dùng) và `prototype/PLAN.md` (thiết kế; trạng thái ở §0, lộ trình ở §16).
- Thư mục gốc (`README.md`, `docs/`, `orchestra.py`, `adapters.py`, `scripts/`, `web/`, `tests/`, `AGENTS.md`): bộ đề xuất và mã nháp do Codex viết, chưa tích hợp với prototype. Không sửa nếu không được yêu cầu. Quy tắc an toàn trong `AGENTS.md` cũng áp dụng cho prototype.

## Chạy test

```bash
cd prototype && PYTHONIOENCODING=utf-8 PYTHONPATH=. python tests/test_e2e.py
```

- 32 test end-to-end với mock agent (`orch/mock.py`), không tốn token. Linux khoảng 60 giây, Windows khoảng 2–3 phút.
- CI (`.github/workflows/ci.yml`) chạy bộ test trên Windows và Linux (3.11, 3.13), macOS không chặn; build wheel rồi chạy `hoatau doctor` từ venv sạch; chạy GitHub Action với team mock.
- Lọc theo tên: thêm một phần tên test vào cuối lệnh, ví dụ `pool`.
- Cần Python 3.11+ và git. Test tự truyền danh tính git, không cần `git config`.
- Test 9router dựng router giả trên 127.0.0.1. Nếu máy có `opencode` thì test gọi opencode thật qua router đó.

## Giới hạn khi chạy trên cloud

Máy cloud không có:
- các agent CLI (codex, agy, opencode …) và login của chúng;
- vault (mã hoá DPAPI, chỉ giải mã được trên máy Windows của người dùng);
- 9router, vốn chỉ nghe trên 127.0.0.1 của máy người dùng.

Vì vậy trên cloud:
- chỉ phát triển code và chạy test mock;
- không chạy `discover --probe`, `run`, `pool test`, `login` với agent thật;
- không chép token hay file auth lên cloud, không mở 9router ra Internet.

Run thật chạy trên máy Windows của người dùng: `git pull`, rồi `python -m orch --ws <dự án> run "<mục tiêu>"` từ `prototype/`.

## Bản đồ module (`prototype/orch/`)

| File | Vai trò |
|---|---|
| `engine.py` | Scheduler tất định quanh bốn điểm quyết định của LLM (plan, review, triage, skills). Định tuyến lỗi, xoay vòng tài khoản khi hết quota, verify, merge. |
| `agents.py` | Agent CLI: discovery, probe, chạy headless trong cây tiến trình (Job Object / process group), parse output, login, đọc quota. |
| `pool.py` | Resource planner: dự báo quota; xếp hạng và pre-test backup pool; ba preset `steady`, `match`, `precise`. |
| `core.py` | Đường dẫn, SQLite của workspace (`.orch/orch.db`), knowledge graph (`kg_search`: FTS5 + vector trigram, hoặc endpoint embeddings nếu `team.json` có `"embeddings"`), khoá engine, vault, JSON strict. |
| `models.py` | Cơ sở dữ liệu model: benchmark Epoch AI, giá OpenRouter, lịch sử run; gợi ý đội hình (`suggest`). |
| `skills.py` | Skill catalog (repo GitHub ghim commit, skill đã cài) và skill architect. |
| `server.py`, `ui.html` | Web UI local (`python -m orch ui`): chỉ 127.0.0.1, có token. Tab Run có sơ đồ DAG (`dag()`); plan đang chờ duyệt sửa được bằng kéo-thả (`planEditor()` → `POST /api/plan` → `Engine.edit_plan`). |
| `mcp.py` | MCP server qua stdio (`python -m orch mcp`): board và knowledge graph thành tool chỉ đọc. Team bật `"mcp": true` thì engine truyền server cho từng lời gọi agent (`agents.mcp_server`). `--control` thêm `run`/`status`/`answer`/`resume`/`cancel`/`doctor` cho phiên Claude Code/Codex của người dùng; agent trong run không bao giờ nhận `--control`. |
| `doctor.py` | `hoatau doctor`: kiểm tra máy và dự án tại chỗ (không mạng, không gọi agent, không in secret). |
| `remote.py` | Worker chạy từ xa: profile ẩn `remote` gọi `remote proxy` (bundle worktree, lease trong bảng `leases`, áp patch); route `/api/lease*` của web UI với token riêng `ORCH_REMOTE_TOKEN`; vòng lặp `remote run` trên máy kia (heartbeat, patch nhị phân). |
| `mock.py` | Agent giả theo kịch bản, dùng cho test. |
| `__main__.py` | CLI `python -m orch <lệnh>`. |

- `prototype/action/`: GitHub Action composite (`action.yml`, `run.py`). `prototype/pyproject.toml`: gói `hoatau`, không dependency; dữ liệu trong `orch/` phải nằm trong `package-data` (test `package_ships_its_data`).
- Đổi schema SQLite: thêm `(version, [câu lệnh])` vào `core.WS_MIGRATIONS` hoặc `HISTORY_MIGRATIONS`, không sửa bản đã phát hành.
- `orch/catalog/`: `agents.json` (profile agent CLI), `skills.json`, `schemas/` (JSON schema cho plan, verdict, triage, handoff, skills).
- Dữ liệu chạy: `~/.orchestra` (`ORCH_HOME`: resources.json, history.db, vault, worktree) và `<dự án>/.orch/`. Không bao giờ commit hai chỗ này.
- `~/.orchestra/agents.json` ghi đè `orch/catalog/agents.json` theo từng profile, chỉ trên máy người dùng (ví dụ port của router). Không sửa catalog trong repo cho nhu cầu của một máy.

## Quy ước

- Chỉ dùng thư viện chuẩn Python. Không thêm dependency.
- Code tối giản. Chỗ cố ý đơn giản hoá có giới hạn thật thì ghi `# ponytail: <giới hạn>, <cách nâng cấp>`.
- Logic không tầm thường cần một check chạy được, thường là một test trong `tests/test_e2e.py`.
- File văn bản dùng LF: `write_text(..., newline="\n")`.

## An toàn (bắt buộc)

- Không đọc hay in nội dung secret. Với file auth chỉ kiểm tra có tồn tại. Từ rollout của codex chỉ đọc object `rate_limits` và timestamp, không đọc nội dung hội thoại.
- Không commit credential, `.orchestra/`, `.orch/`, log. Repo **public**: quét secret trước khi push. Không ghi email của người dùng hay chi tiết bảo mật máy họ (cấu hình 9router) vào repo. Token giả trong test (`ORCH_REMOTE_TOKEN`, key embeddings) chỉ sinh trong test.
- Output của model là đề xuất không tin cậy. Hai điểm va chạm với `AGENTS.md` (`PLAN.md` §13) đã có opt-in (`verify_allow`, `"skills": "propose"`). Mặc định giữ hành vi cũ; bật hay không do người dùng quyết định.
- Không sửa dữ liệu hay config global của tool người dùng. Test opencode dùng `XDG_DATA_HOME` riêng.
- Phải hỏi người dùng trước khi: tải hoặc cài gói; login, tạo tài khoản, nhập key; pre-test model trả phí (tốn quota).
- 9router: không bật MITM, cert hay DNS. Khuyến nghị `HOSTNAME=127.0.0.1`, `REQUIRE_API_KEY=true`, đổi `INITIAL_PASSWORD`, tắt Cloud Sync. Không sửa cấu hình hay dừng/khởi động lại router của người dùng khi chưa được phép.
- Pre-test hoặc probe qua router tốn quota subscription phía sau nó: hỏi trước.
- Không đổi cài đặt hệ thống hay bảo mật (ví dụ sandbox Windows của codex), chỉ khuyến nghị.
- Runner từ xa chỉ nối qua 127.0.0.1 hoặc đường hầm SSH; không đổi firewall, không mở port UI ra mạng.
- Gửi fact ra endpoint embeddings chỉ khi người dùng bật `"embeddings"` trong `team.json`.
- Lớp lỗi (`agents.classify`) chỉ đọc lỗi của CLI và stderr, không đọc transcript stdout. Lệnh verify dùng `agents.verify_env()` (danh sách cho phép), không dùng `clean_env()`.

## Bẫy đã gặp

- opencode lấy thư mục dự án từ biến `PWD`, không phải cwd thật. `agents.spawn()` đặt `PWD` bằng cwd; đừng bỏ dòng đó.
- Windows: đặt `PYTHONIOENCODING=utf-8` khi in tiếng Việt.
- `Path.write_text` trên Windows ghi CRLF nếu không truyền `newline="\n"`.
- Heredoc trong bash biến `\\n` thành `\n`. Sửa chuỗi có escape bằng công cụ Edit.
- Chỉ codex để lại số liệu quota (`rate_limits` trong rollout). agy, opencode và router: engine học từ lỗi trả về.
- Hàm `git()` của engine decode và strip output, làm hỏng patch nhị phân: dùng `_git(..., text=False)`.
- `git bundle create f <sha>` báo "Refusing to create empty bundle": tạo ref tạm, bundle xong thì xoá (`remote.snapshot`).
- Windows: trả lời HTTP khi chưa đọc hết body thành connection reset (WinError 10053); handler của UI đọc body trước.
- Máy người dùng: `.agents/` ở gốc repo là dữ liệu đang dùng của Antigravity IDE, bị bỏ qua qua `.git/info/exclude`. Không xoá, không commit. Trước khi dọn file untracked, xem thời gian sửa và tiến trình đang chạy.

## Việc tiếp theo

Lộ trình ở `prototype/PLAN.md` §0 và §16. P1 xong. P2 xong phần code: sơ đồ DAG, sửa plan bằng kéo-thả, MCP server, embeddings, worker chạy từ xa, UI pha 1–3. Đợt review 2026-10-04 đã sửa phân loại lỗi, lệnh verify của bản amend, môi trường của verify, LF. P3 (sản phẩm, hướng A + E): tên Hoatau, Apache-2.0, gói `hoatau`, migration DB, `doctor`, CI, MCP `--control`, GitHub Action beta (`PLAN.md` §16).

Đang chờ người dùng:
1. Quyết định có bật hai opt-in ở §13 trong `team.json` hay không.
2. Nối 9router: người dùng tự kiểm tra cấu hình an toàn (§13), login dashboard và provider, `vault set NINEROUTER_API_KEY`, rồi `discover --only opencode@9router`.
3. Tự chạy `models refresh`, `skills refresh` và `login claude`.
4. Thử worker chạy từ xa với CLI thật qua `ssh -R` (bộ test 27/27 đã pass trên Windows).
5. UI pha 4 (`docs/UIUX.md` §12): audit bằng web-design-guidelines bản ghim (cần cài), Narrator, ảnh chụp README.
6. Giữ tên `hoatau` trên PyPI (cần tài khoản của người dùng); thử GitHub Action với agent thật và API key.

Ưu tiên tiếp theo: vài run thật trên repo thật; lưu đầu ra thật của CLI mới vào `prototype/docs/probes/` làm fixture cho parser.

## Quy ước git

- Mỗi tính năng một commit. Không dùng `git stash` trần. Chỉ push khi người dùng bảo.
