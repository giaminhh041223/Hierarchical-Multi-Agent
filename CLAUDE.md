# CLAUDE.md

Bối cảnh cho Claude Code (local hoặc cloud) khi làm việc trong repo này. Người dùng nói tiếng Việt: trả lời và viết tài liệu bằng tiếng Việt.

## Repo gồm gì

- `prototype/`: **code đang phát triển**. Orchestra là môi trường local, lấy cảm hứng từ n8n, điều phối nhiều AI coding agent CLI (codex, agy/Antigravity, opencode, claude, gemini …):
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

- 24 test end-to-end với mock agent (`orch/mock.py`), không tốn token. Linux khoảng 40 giây, Windows khoảng 2–3 phút.
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
| `core.py` | Đường dẫn, SQLite của workspace (`.orch/orch.db`), khoá engine, vault, JSON strict. |
| `models.py` | Cơ sở dữ liệu model: benchmark Epoch AI, giá OpenRouter, lịch sử run; gợi ý đội hình (`suggest`). |
| `skills.py` | Skill catalog (repo GitHub ghim commit, skill đã cài) và skill architect. |
| `server.py`, `ui.html` | Web UI local (`python -m orch ui`): chỉ 127.0.0.1, có token. Tab Run có sơ đồ DAG (`dag()`); plan đang chờ duyệt sửa được bằng kéo-thả (`planEditor()` → `POST /api/plan` → `Engine.edit_plan`). |
| `mcp.py` | MCP server qua stdio (`python -m orch mcp`): board và knowledge graph thành tool chỉ đọc. Team bật `"mcp": true` thì engine truyền server cho từng lời gọi agent (`agents.mcp_server`). |
| `mock.py` | Agent giả theo kịch bản, dùng cho test. |
| `__main__.py` | CLI `python -m orch <lệnh>`. |

- `catalog/`: `agents.json` (profile agent CLI), `skills.json`, `schemas/` (JSON schema cho plan, verdict, triage, handoff, skills).
- Dữ liệu chạy: `~/.orchestra` (`ORCH_HOME`: resources.json, history.db, vault, worktree) và `<dự án>/.orch/`. Không bao giờ commit hai chỗ này.
- `~/.orchestra/agents.json` ghi đè `catalog/agents.json` theo từng profile, chỉ trên máy người dùng (ví dụ port của router). Không sửa catalog trong repo cho nhu cầu của một máy.

## Quy ước

- Chỉ dùng thư viện chuẩn Python. Không thêm dependency.
- Code tối giản. Chỗ cố ý đơn giản hoá có giới hạn thật thì ghi `# ponytail: <giới hạn>, <cách nâng cấp>`.
- Logic không tầm thường cần một check chạy được, thường là một test trong `tests/test_e2e.py`.
- File văn bản dùng LF: `write_text(..., newline="\n")`.

## An toàn (bắt buộc)

- Không đọc hay in nội dung secret. Với file auth chỉ kiểm tra có tồn tại. Từ rollout của codex chỉ đọc object `rate_limits` và timestamp, không đọc nội dung hội thoại.
- Không commit credential, `.orchestra/`, `.orch/`, log. Repo có thể public: quét secret trước khi push.
- Output của model là đề xuất không tin cậy. Hai điểm va chạm với `AGENTS.md` (`PLAN.md` §13) đã có opt-in (`verify_allow`, `"skills": "propose"`). Mặc định giữ hành vi cũ; bật hay không do người dùng quyết định.
- Không sửa dữ liệu hay config global của tool người dùng. Test opencode dùng `XDG_DATA_HOME` riêng.
- Phải hỏi người dùng trước khi: tải hoặc cài gói; login, tạo tài khoản, nhập key; pre-test model trả phí (tốn quota).
- 9router: không bật MITM, cert hay DNS. Khuyến nghị `HOSTNAME=127.0.0.1`, `REQUIRE_API_KEY=true`, đổi `INITIAL_PASSWORD`, tắt Cloud Sync. Không sửa cấu hình hay dừng/khởi động lại router của người dùng khi chưa được phép.
- Pre-test hoặc probe qua router tốn quota subscription phía sau nó: hỏi trước.
- Không đổi cài đặt hệ thống hay bảo mật (ví dụ sandbox Windows của codex), chỉ khuyến nghị.

## Bẫy đã gặp

- opencode lấy thư mục dự án từ biến `PWD`, không phải cwd thật. `agents.spawn()` đặt `PWD` bằng cwd; đừng bỏ dòng đó.
- Windows: đặt `PYTHONIOENCODING=utf-8` khi in tiếng Việt.
- `Path.write_text` trên Windows ghi CRLF nếu không truyền `newline="\n"`.
- Heredoc trong bash biến `\\n` thành `\n`. Sửa chuỗi có escape bằng công cụ Edit.
- Chỉ codex để lại số liệu quota (`rate_limits` trong rollout). agy, opencode và router: engine học từ lỗi trả về.

## Việc tiếp theo

Xem `prototype/PLAN.md` §0 và §16.

Đang chờ người dùng:
1. Quyết định có bật hai opt-in ở §13 trong `team.json` hay không.
2. Nối 9router: người dùng tự kiểm tra cấu hình an toàn (§13), login dashboard và provider, `vault set NINEROUTER_API_KEY`, rồi `discover --only opencode@9router`.
3. Tự chạy `models refresh`, `skills refresh` và `login claude`.

P1 ở §16 đã xong. P2: đã có sơ đồ DAG, sửa plan bằng kéo-thả và MCP server; đang làm embeddings cho knowledge graph và worker chạy từ xa (xem §16).
