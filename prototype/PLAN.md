# Orctram (trước đây: Orchestra): kế hoạch chi tiết và thiết kế

Đây là bản prototype chạy được của một môi trường local điều phối nhiều AI coding agent, lấy cảm hứng từ n8n. Tài liệu ghi lại:
- thiết kế đã chốt sau hai vòng trao đổi giữa Claude (lead) và Codex (reviewer);
- cách prototype hiện thực từng phần;
- lộ trình tiếp theo.

Hướng dẫn sử dụng nằm ở [README.md](README.md).

## 0. Trạng thái (2026-10-05)

| Hạng mục | Trạng thái |
|---|---|
| Engine, CLI, web UI, vault, discovery, model DB, skill architect, knowledge graph, resource planner, MCP server (cả chế độ `--control`), worker chạy từ xa, `doctor`, GitHub Action | Chạy được. Chỉ dùng thư viện chuẩn Python 3.11+. Đóng gói thành lệnh `orctram` (`pyproject.toml`, chưa lên PyPI), license Apache-2.0. |
| Test end-to-end | 33/33 PASS với mock agent (không tốn token) trên Linux (Python 3.11). GitHub Actions chạy bộ test trên Windows và Linux (3.11, 3.13), macOS (không chặn), cùng job wheel và GitHub Action. Trên máy Windows của bạn đã pass 27 test (trước đợt đóng gói). |
| Adapter đã kiểm chứng cờ dòng lệnh trên máy này | <ul><li>`codex` 0.153.4.</li><li>`agy` 1.2.15.</li><li>`opencode` 1.18.34, profile `opencode@free`:<ul><li>8/10 model free trả lời được;</li><li>`big-pickle` và `fledge-alpha-free` qua pre-test code.</li></ul></li></ul> |
| Run thật | Smoke run `20261003-021406` trên một repo đồ chơi đã xong và được duyệt. Đội: lead codex, worker codex + agy, reviewer agy. |
| Chưa kiểm chứng | <ul><li>`claude`: chưa đăng nhập.</li><li>`gemini`, `cursor-agent`.</li><li>`claude@zai`: chưa có key.</li><li>`opencode@9router`: mới thử với router giả. 9router đã có trên máy nhưng chưa nối (§16 P0).</li><li>Worker chạy từ xa với CLI thật qua đường hầm SSH: mới qua test với mock agent (§10).</li></ul> |
| Chưa chạy | <ul><li>`models refresh` / `skills refresh`: tải dữ liệu từ Internet, bạn tự chạy.</li><li>Nối 9router: cần bạn thao tác (§16 P0).</li></ul> |

## 1. Ý tưởng cốt lõi

**Engine tất định, LLM chỉ ở điểm quyết định.** Giống n8n, một workflow engine điều phối các node.
- Phần lớn việc là code: lập lịch DAG, git, kiểm tra phạm vi, chạy verify, định tuyến lỗi, ngân sách token.
- Model chỉ được gọi ở 6 điểm cần phán đoán: lập plan, review plan, triage lỗi, chọn skill, review cuối, bổ sung plan (amend).
- Kết quả: rẻ, tái lập được, và test được bằng mock.

**Lead không giữ trạng thái (stateless).** Mỗi lần gọi lead, prompt được dựng lại từ DB: goal, đội hình, repo map, plan, các lần thử, facts.
- Không kéo theo transcript dài, nên tiết kiệm token.
- Đổi model lead lúc nào cũng được.
- Engine crash không làm mất "trí nhớ".

**Một file SQLite làm bảng đen (blackboard) cho mọi bên.** Engine ghi; CLI, UI và agent đọc (agent đọc với `mode=ro`).

**Mỗi worker một git worktree riêng, chỉ engine được commit và merge.** Kết quả được tích hợp vào nhánh `orch/<run>/main`, không bao giờ vào nhánh của bạn. Bạn tự merge khi hài lòng.

## 2. Yêu cầu → thành phần

| # | Yêu cầu | Thành phần trong prototype |
|---|---|---|
| 1 | Lead là model mạnh nhất, nhận yêu cầu từ bạn | <ul><li>Vai trò `lead` trong `team.json`.</li><li>Gợi ý theo chỉ số ECI (`models suggest`).</li><li>Nhận goal qua `orch run` hoặc tab Run.</li></ul> |
| 2 | Tìm agent, tài khoản, model rồi hỏi bạn chọn | <ul><li>`orch discover [--probe]` ghi ra `~/.orchestra/resources.json`.</li><li>`orch init` (hoặc tab Team) đề xuất đội hình; bạn chấp nhận hoặc chọn lại.</li><li>Probe xác nhận model thực sự dùng được.</li></ul> |
| 3 | Workspace có rule riêng cho từng worker và kênh chung; tối ưu context, token, thời gian | <ul><li>Thư mục `<project>/.orch/`, gồm `rules/<vai trò hoặc worker>.md`.</li><li>`orch.db` chứa tasks, events (kênh chung) và facts.</li><li>Packet gọn (§9).</li></ul> |
| 4 | Lead cùng reviewer lập plan chi tiết, rồi lead giao việc | Job PLAN, lần lượt:<ol><li>Lead viết plan JSON.</li><li>Engine kiểm tra DAG.</li><li>Reviewer review tối đa 2 vòng.</li><li>Bạn duyệt.</li><li>Scheduler giao task.</li></ol> |
| 5 | Lead xử lý lỗi, vượt quyền thì ping bạn; task lỗi chờ, task khác vẫn chạy | <ul><li>`route()` tất định, rồi lead triage.</li><li>Ngoài quyền lead thì chuyển `pending_user` (inbox + webhook).</li><li>Task độc lập vẫn chạy tiếp.</li></ul> |
| 6 | Khu vực nhập API key, môi trường kết nối, đăng nhập tài khoản agent | <ul><li>Vault mã hoá bằng DPAPI (`orch vault`, tab Vault).</li><li>`orch login <agent>` mở luồng đăng nhập của chính CLI đó.</li></ul> |
| 7 | (tuỳ chọn) DB benchmark model, mạng thông tin model riêng | <ul><li>`~/.orchestra/models.json` lấy từ Epoch AI và OpenRouter.</li><li>`~/.orchestra/history.db` ghi kết quả từng lần gọi, để thẻ model có số liệu "của mình".</li></ul> |
| 8 | Skill architect trên mọi task: tìm skill/plugin GitHub, cài, phân phối | Task SKILLS mỗi run:<ul><li>Chọn tối đa 3 skill từ chỉ mục curated.</li><li>Cài theo commit đã ghim, kèm sha256 và quét tĩnh.</li><li>Đặt vào worktree của đúng task.</li><li>Repo ngoài danh sách phải chờ bạn duyệt.</li></ul> |
| 9 | (tuỳ chọn) Knowledge graph nhanh, dùng chung | <ul><li>Bảng SQLite FTS5 `facts` và bảng `links`; tìm bằng từ khoá kết hợp vector (§10).</li><li>Agent tra bằng `python -m orch kg search`.</li></ul> |
| 10 | Resource determine: lên kế hoạch tài nguyên trước, gồm:<ul><li>usage còn bao nhiêu, bao giờ hồi;</li><li>model tương đương nằm sẵn trong pool backup đã test trước;</li><li>hẹn giờ bật lại model chính.</li></ul> | Resource planner (`orch/pool.py`, §6.1):<ul><li>Đầu mỗi run: đọc quota, ghi mục Resources trong `plan.md`, khoá trước tài khoản đã hết.</li><li>`orch pool plan`: xếp hạng theo tiêu chí bạn tick hoặc 3 preset, pre-test, lưu backup riêng cho từng worker.</li><li>Hết usage giữa chừng: backup làm tiếp ngay trong worktree đó; tới giờ reset thì trả task về model chính.</li></ul> |
| — | Trao đổi với Codex, lập plan chi tiết, làm thử như một dự án | §14 và [docs/codex/](docs/codex/) |

## 3. Kiến trúc

```
 Bạn ──► CLI (python -m orch …) ──┐           ┌──► Web UI 127.0.0.1 (python -m orch ui)
                                  ▼           ▼
          <project>/.orch/orch.db  (SQLite: tasks · attempts · plans · events · facts · links · skills · meta)
                                  ▲
                                  │  một engine mỗi workspace (khoá file của OS)
                         Engine (orch/engine.py)
          lập lịch DAG · định tuyến lỗi · tích hợp git · verify · ngân sách · webhook
                                  │  spawn qua adapter manifest (orch/catalog/agents.json), trong Windows Job Object
       ┌──────────────┬───────────┴───┬────────────────┬───────────────────┐
     codex         claude            agy        opencode/gemini/…       mock (test)
       │  mỗi worker chạy trong worktree riêng: ~/.orchestra/wt/<repo>-<hash>/<run>/<task>
       ▼
 nhánh orch/<run>/<task> ──(engine: commit → merge tip → scope → verify → ff-only)──► orch/<run>/main
```

| Module | Vai trò |
|---|---|
| [orch/engine.py](orch/engine.py) | Scheduler, máy trạng thái, tích hợp git, định tuyến lỗi, dựng packet, khôi phục sau crash |
| [orch/core.py](orch/core.py) | Workspace (SQLite), knowledge graph, vault DPAPI, che secret (`redact`), kiểm tra JSON contract, khoá engine |
| [orch/agents.py](orch/agents.py) | Discovery, probe, đăng nhập, spawn tiến trình (Job Object), parser đầu ra, phân loại lỗi, môi trường tối thiểu |
| [orch/models.py](orch/models.py) | DB model: refresh, thẻ model, gợi ý đội hình |
| [orch/skills.py](orch/skills.py) | Chỉ mục skill, cài đặt, skill architect, đặt skill vào worktree, duyệt repo |
| [orch/server.py](orch/server.py), [orch/ui.html](orch/ui.html) | Web UI local |
| [orch/mcp.py](orch/mcp.py) | MCP server qua stdio: board và knowledge graph thành tool chỉ đọc |
| [orch/bench.py](orch/bench.py) | `bench`: một agent làm một mình và cả đội, cùng commit gốc, chấm bằng cùng lệnh `--check` |
| [orch/doctor.py](orch/doctor.py) | `doctor`: kiểm tra máy và dự án tại chỗ (không mạng, không gọi agent, không in secret) |
| [action/](action/) | GitHub Action dạng composite: `action.yml` và `run.py` (đặt team, chạy run, đẩy nhánh, mở PR) |
| [orch/remote.py](orch/remote.py) | Worker chạy từ xa: proxy phía engine (bundle, lease, áp patch), route lease của web UI, vòng lặp runner |
| [orch/\_\_main\_\_.py](orch/__main__.py) | CLI |
| [orch/mock.py](orch/mock.py) | Agent giả theo kịch bản, để test không tốn token |
| [orch/catalog/](orch/catalog/) | `agents.json` (adapter), `skills.json` (nguồn curated), `schemas/*.json` (contract). Nằm trong gói nên có sẵn khi `pip install`; `models.json` (có sau `models refresh`) nằm ở `~/.orchestra/`. |

Dữ liệu được lưu ở hai nơi.

**`<project>/.orch/`.** Engine tự thêm thư mục này vào `.git/info/exclude`, nên nó không lọt vào commit. Nội dung:
- `orch.db`, `team.json`, `rules/`;
- `runs/<run>/plan.md` và `runs/<run>/report.md`;
- `runs/<run>/attempts/<task>-<n>-<kind>/`: prompt, stdout, stderr, đầu ra verify, patch bị bỏ;
- `engine.log`, khi engine được khởi động từ UI.

**`~/.orchestra/`** (đổi vị trí bằng `ORCH_HOME`):
- `resources.json`, `vault.dpapi`, `history.db`;
- `skills/`: chỉ mục và cache theo commit;
- `wt/`: các worktree.

## 4. Vòng đời một run

1. **Khởi tạo** (`orch run "<goal>"`).
   - Cần repo git có ít nhất một commit.
   - Thay đổi chưa commit sẽ bị cảnh báo, vì agent bắt đầu từ `HEAD`.
   - Engine tạo nhánh tích hợp `orch/<run>/main` trong một worktree riêng, cùng task `PLAN`.
2. **Lập plan.** Lead chạy ở chế độ chỉ đọc và trả về plan JSON. Engine kiểm tra:
   - id hợp lệ, không trùng, không tái dùng, không dùng id dành riêng;
   - assignee có trong đội;
   - dependency tồn tại và không tạo chu trình;
   - scope được chuẩn hoá và không chạm `.orch/`;
   - acceptance và verify không rỗng.

   Nếu sai, lead được sửa một lần (repair).
3. **Review plan.** Reviewer trả verdict gồm các issue `blocker` hoặc `advisory`, tối đa 2 vòng.
   - Ở vòng sửa, engine dùng lại session của lead nếu adapter hỗ trợ resume, và chỉ gửi phần chênh lệch.
   - Còn blocker sau 2 vòng thì engine hỏi bạn.
4. **Duyệt.** Engine ghi `plan.md`.
   - Trả lời `yes` / `có` / `duyệt` để bắt đầu, hoặc viết góp ý để lead lập lại plan.
   - Hoặc tự sửa trên web UI (nút **Edit plan**): kéo từ task này sang task kia để thêm dependency, bấm vào đường nối để bỏ, chọn worker cho từng task. Bảng bên dưới sơ đồ làm được mọi việc đó bằng bàn phím.
     - Bản sửa qua đúng các kiểm tra của plan do lead lập (bước 2), được lưu thành phiên bản kế tiếp và vẫn chờ `yes`.
     - Bị từ chối nếu plan đã sang phiên bản khác hoặc đã có câu trả lời đang được xử lý. Một `yes` đọc trước khi bản sửa được lưu không hiện thực hoá phiên bản cũ.
   - `--yes` hoặc `auto_approve` bỏ qua bước này.
5. **Hiện thực hoá.** Trong một transaction và đúng một lần, engine tạo:
   - các task công việc;
   - task `SKILLS` (nếu bật);
   - task `REVIEW`, phụ thuộc vào mọi task công việc.
6. **Skill architect** chạy trước. Task công việc chờ SKILLS xong để skill có sẵn trong worktree.
7. **Thực thi song song.** Task sẵn sàng (mọi dependency đã `done`) được chạy trong giới hạn `max_parallel` và số slot của từng worker. Worker nhận packet, sửa code trong worktree, rồi kết thúc bằng handoff JSON.
8. **Tích hợp.** Chạy tuần tự, dưới khoá:
   1. Commit tạm.
   2. Merge tip của nhánh tích hợp vào.
   3. Chặn nếu còn dấu xung đột.
   4. Kiểm tra phạm vi (`--no-renames`).
   5. Chạy verify trên cây đã gộp.
   6. Tạo **một commit squash** chứa đúng cây vừa verify.
   7. Ghi `commit_sha` bằng compare-and-set (`verifying → integrating`).
   8. `merge --ff-only`.
   9. `finalize`: chuyển `done`, ghi facts và links trong một transaction, đúng một lần.
9. **Review cuối.** Engine chạy lại mọi verify trên cây tổng, reviewer đọc diff.
   - Có blocker thì lead bổ sung task (amend, tối đa `max_amend` lần), rồi review lại.
   - Hết lượt amend thì engine hỏi bạn: `accept`, hoặc đưa hướng dẫn.
10. **Kết thúc.**
    - Engine ghi `report.md`: task, commit, token và chi phí theo agent/model, câu hỏi còn chờ.
    - Engine dọn worktree. Việc chưa tích hợp được giữ lại thành commit wip trên nhánh task.
    - Engine gửi webhook.

    Bạn merge khi hài lòng: `git merge orch/<run>/main`.

## 5. Máy trạng thái

Trạng thái của task:

```
todo ──► running ──► verifying ──► integrating ──► done
  ▲         │            │              │
  │         └────────────┴──────────────┴──► route(): todo (thử lại / backoff) | needs_lead | pending_user | failed | cancelled
  │
  ├── needs_lead ──(lead triage)──► todo (retry / reassign) | pending_user | failed | cancelled
  └── pending_user ──(bạn trả lời)──► todo | cancelled        (PLAN / REVIEW / BUDGET xử lý riêng, xem §6)
```

- `done`, `failed`, `cancelled` là trạng thái cuối.
- Khi một task thất bại hoặc bị huỷ, các task phụ thuộc vào nó bị huỷ theo, trừ REVIEW (vì REVIEW còn đánh giá cả phần thất bại).
- Chờ dependency là điều kiện lập lịch, không phải một trạng thái.
- Backoff khi bị rate limit dùng `eligible_at`.
- Mọi chuyển trạng thái quan trọng là compare-and-set (`UPDATE … WHERE status=?`), nên không có hai luồng cùng chuyển một task.

Trạng thái của run:
- Đang chạy → `waiting` khi chỉ còn việc chờ bạn (cờ `--exit-on-wait`, mã thoát 3) → `done` | `failed` | `cancelled`.
- `done` nghĩa là review cuối đã duyệt.
- Engine dừng giữa chừng (Ctrl+C, crash) thì chạy `orch resume`.

**Khôi phục sau crash (`reconcile`):**
- Task `integrating` có `commit_sha` đã nằm trong nhánh tích hợp: hoàn tất, đúng một lần.
- Task `integrating` chưa có commit trong nhánh: verify lại.
- Tiến trình agent mồ côi chỉ bị kill khi khớp cả PID **lẫn** thời điểm tạo, nên không bao giờ kill nhầm một PID đã bị tái sử dụng.
- Task `running` quay về `todo`, kèm ghi chú nhắc worker kiểm tra lại worktree.

## 6. Định tuyến lỗi (tất định, trước khi tốn thêm token)

| Tình huống | Xử lý |
|---|---|
| `auth` (chưa đăng nhập, 401, sai key) | Hỏi bạn ngay. Bạn có thể:<ul><li>chạy `orch login <agent>` hoặc `orch vault set`, rồi trả lời `retry`;</li><li>hoặc trả lời `reassign <worker>` / `cancel`.</li></ul> |
| `quota` (hết usage của tài khoản) | Khoá cả tài khoản tới giờ reset, rồi xoay vòng sang backup (§6.1). |
| `rate_limit` (429) | Chờ 60 s · 2ⁿ (tối đa 900 s), 3 lần. Lần thứ 4 coi như hết usage: khoá tài khoản 5 phút rồi xoay vòng. |
| `conflict` (xung đột merge), `crashed` | Thử lại tự động. Worker nhận các file có dấu xung đột và tự gộp. |
| `scope`, `verify`, `invalid`, `error` ở lần đầu | Thử lại một lần, kèm bằng chứng (lỗi verify, file ngoài phạm vi …). |
| Lỗi lặp lại, `timeout`, `blocked` (worker đặt câu hỏi), `failed` | Chuyển `needs_lead`. Lead triage và chọn một trong: `retry` (kèm chỉ dẫn), `reassign`, `ask_user`, `fail`, `cancel`. |
| Không gọi được lead | Hỏi bạn. |
| Đã thử ≥ 6 lần (`HARD_CAP`) | Hỏi bạn. |
| Vượt ngân sách token | Tạo task cổng `BUDGET<n>` và ngừng khởi động lời gọi mới. Bạn trả lời ngân sách mới (`500k`, `2m`) hoặc `stop`. |

Lớp lỗi lấy từ lỗi có cấu trúc của chính CLI và stderr, không bao giờ từ transcript stdout của agent: transcript trích dẫn dự án (route `/login`, "line 429", file `quota.py`), và một lần đoán nhầm `quota` khoá cả tài khoản. Mã HTTP chỉ được tính khi đứng cạnh một từ như `status`, `error`, `HTTP`. Các mẫu được kiểm bằng đầu ra thật trong [docs/probes/](docs/probes/).

Hai nguyên tắc:
- Không bao giờ lặp lại y hệt một lần thử quá một lần.
- Session hỏng hoặc treo bị bỏ, để không "đầu độc" lần thử sau.

Bạn có thể trả lời:
- `yes`, `retry`, `reassign <worker>`;
- `cancel` (hoặc `hủy`, `bỏ qua`);
- văn bản tự do, được chuyển thành ghi chú cho lần thử sau.

### 6.1 Hết usage: xoay vòng và resource planner

Mục tiêu: hết usage là chuyện thường ngày, không phải lỗi, nên engine tự xử lý bằng code, không tốn token. Cách dùng và bảng tiêu chí: [README](README.md#hết-usage-xoay-vòng-và-pool-backup).

**Đơn vị là tài khoản, không phải worker.**
- Tài khoản = `agents.account(agent, model)`, tức một quota. Thường đó là agent id (`codex`, `agy`, `opencode@free`, …).
- Profile router (`opencode@9router`) có một tài khoản cho mỗi tiền tố provider của model id (`if/…` → `opencode@9router/if`).
  - `shares` ánh xạ tiền tố nào cũng là subscription của một CLI về tài khoản của CLI đó (`cx/…` → `codex`), vì hai bên hết usage cùng lúc.
- `cool(acct)` ghi `cool:<acct>` vào `ws.meta`. Mọi worker và vai trò dùng tài khoản đó cùng dừng.
- `account_max` trong `team.json` (ví dụ `{"codex": 1}`) giới hạn số task work chạy song song trên một tài khoản, cho trường hợp nhiều worker dùng chung một subscription. Mặc định không giới hạn.
- Giờ mở khoá lấy theo thứ tự:
  1. giờ reset trong thông báo lỗi của CLI;
  2. bản ghi quota của chính CLI: codex ghi `rate_limits` vào rollout, engine chỉ đọc object này;
  3. `cooldown` trong `team.json`: 3600 s; 300 s cho rate limit lặp lại.

**Xoay vòng (`rotate`).**
- Reset trong vòng `wait_reset` (600 s) hoặc không có ai thay: task chờ.
- Nếu không, `spare()` chọn người thay:
  1. Worker còn slot trống trước.
  2. Rồi theo thứ tự ưu tiên:
     1. backup có `for` chứa worker chính;
     2. backup chung;
     3. backup của worker khác;
     4. worker chính khác.
  3. Không bao giờ chọn tài khoản đang khoá.
- Task đã chạy dở: worktree được giữ nguyên, và ghi chú cho backup nói rõ có phần việc dở. Task chưa chạy lần nào thì không có ghi chú đó.
- `home:<tid>` nhớ worker chính. Khi tài khoản chính hết khoá, `schedule()` trả task về worker chính ở ranh giới lần thử kế tiếp. Engine không cắt ngang lời gọi đang chạy.
- Xoay vòng trước: task còn trong hàng đợi của tài khoản đang khoá được chuyển ngay, không tốn một lời gọi thất bại.
- Lead, reviewer, skill architect hết usage: `ask()` gọi một vai trò hoặc worker khác đứng thay.

**Resource planner (`check_resources`, đầu mỗi vòng lặp của engine).**
- Đọc quota từng tài khoản, ghi mục `## Resources` trong `plan.md`.
- Khoá trước tài khoản đã hết.
- Cảnh báo tài khoản "at risk" (có thể hết trước giờ reset theo tốc độ dùng hiện tại) mà worker của nó chưa có backup.
- Agent không có bản ghi quota: học từ lỗi của chúng.

**Pool backup (`orch pool plan`).**
- Ứng viên là mọi cặp (tài khoản, model) đã đăng nhập, trừ:
  - tài khoản của chính worker chính;
  - tài khoản đang khoá hoặc đã dùng ≥ 90%;
  - cặp đang là worker chính;
  - cặp có lần pre-test gần nhất lỗi nặng: `auth`, `model`, `missing`, `error`, `invalid`, `blocked`.
- Điểm = Σ wᵢ·sᵢ / Σ wᵢ.
  - Tiêu chí chưa có dữ liệu tính 0,5.
  - `conf` = phần trọng số có dữ liệu thật.
  - Tài khoản at risk chỉ giữ `RISK` = 0,75 số điểm.
- Nguồn dữ liệu:
  - `c`/`r`/`n`: percentile benchmark công khai (`models refresh`);
  - `s`/`h`/`q`: lịch sử của chính bạn và pre-test.
- Pre-test là một task code nhỏ (FizzBuzz) theo đúng hợp đồng handoff.
  - Khi một trong n/c/r/h có trọng số ≥ 3 (preset `match` và `precise`), pre-test dùng bài khó hơn: chuyển đổi số La Mã hai chiều và từ chối mọi chuỗi không chuẩn (`IIII`, `VX`, `IM` …). Model yếu hay báo "done" mà bỏ sót đúng các trường hợp này. Cờ `--hard` ép dùng bài khó.
  - Khi cần bài khó, chỉ kết quả bài khó trong 24 giờ qua mới được tính là còn mới.
  - Engine tự chạy lệnh kiểm tra; "done" mà kiểm tra trượt thì ghi `verify`, tức ảo giác.
  - Các tài khoản chạy song song; trong cùng tài khoản chạy lần lượt.
  - Kết quả ghi vào `history.db` với role `pool`.
- Ba preset trả lời ba tình huống:
  - `steady`: gián đoạn ngắn, cần chảy liên tục. Ưu tiên ổn định, nhanh, free.
  - `match`: gián đoạn dài, task cốt lõi. Ưu tiên năng lực gần model chính, chỉ dùng model có benchmark.
  - `precise`: task nhạy cảm. Ưu tiên trung thực và suy luận.

## 7. Hợp đồng JSON

Mỗi lời gọi agent phải trả về đúng một object theo schema nghiêm ngặt trong [orch/catalog/schemas/](orch/catalog/schemas/):
- mọi trường đều bắt buộc;
- `additionalProperties: false`;
- trường tuỳ chọn dùng `null`.

Engine không tin CLI và tự kiểm tra lại:
1. Từ chối key trùng, NaN/Infinity, sai kiểu, phản hồi lớn hơn 256 KB.
2. Kiểm tra ngữ nghĩa.
3. Nếu sai, cho một lần sửa (repair); vẫn sai thì đánh dấu `invalid`.

| Contract | Ai trả | Nội dung chính | Kiểm tra ngữ nghĩa thêm |
|---|---|---|---|
| `plan` | lead | `tasks[]`: id, title, assignee, deps, acceptance, scope_paths, verify (mảng argv) | DAG, id, scope, verify (§4, bước 2) |
| `verdict` | reviewer | `verdict` (approve/revise), `issues[]` {task_id, severity blocker/advisory, message} | — |
| `handoff` | worker | status (done/blocked/failed), summary, files, decisions, facts, question | <ul><li>`blocked` phải kèm câu hỏi.</li><li>`done` chỉ có nghĩa "sẵn sàng để verify".</li></ul> |
| `triage` | lead | action (retry/reassign/ask_user/fail/cancel), note, assignee, question | <ul><li>`reassign` cần một worker hợp lệ.</li><li>`ask_user` cần câu hỏi.</li></ul> |
| `skills` | skill architect | `skills[]` {id, tasks, reason} | Chỉ chấp nhận id có trong chỉ mục, hoặc URL repo GitHub (thành đề xuất). |

Contract luôn có trong prompt. Ngoài ra:
- codex nhận schema qua cờ `--output-schema`;
- claude và agy nhận qua cờ `--json-schema`;
- các CLI còn lại chỉ có schema trong prompt.

Dù nhận theo cách nào, engine vẫn kiểm tra như nhau.

## 8. Adapter và tiến trình

Adapter là dữ liệu, không phải class. Mỗi mục trong [orch/catalog/agents.json](orch/catalog/agents.json) khai báo:
- binary;
- cờ `run` và `resume`, với các placeholder `{model} {session} {out} {schema} {schema_json} {prompt} {mode}`;
- chế độ `rw` (worker sửa file) và `ro` (lead, reviewer, probe);
- cách nhận prompt: stdin hoặc tham số (prompt dài hơn 24.000 ký tự đi qua file);
- file và biến môi trường chứng thực;
- lệnh đăng nhập;
- nguồn danh sách model;
- parser đầu ra;
- cách truyền MCP server theo từng lời gọi (`mcp`, §10).

Thêm một CLI mới = thêm một mục JSON, cộng một parser nhỏ nếu định dạng đầu ra lạ.

| Agent | Trạng thái trên máy này |
|---|---|
| `codex` | Đã kiểm chứng:<ul><li>Lệnh chạy: `codex -a never exec --json --skip-git-repo-check -s <mode> -m <model> -o <out> --output-schema <schema> -`.</li><li>Resume bằng thread id với `-c sandbox_mode=…`, vì `resume` không nhận `-s`/`-C`.</li><li>Token đọc từ `turn.completed.usage`.</li><li>Có trong danh sách model chưa chắc dùng được (một model bị từ chối với tài khoản ChatGPT), nên luôn probe.</li><li>Quota (`"usage": "codex_rollouts"`): đọc `rate_limits` trong rollout của codex, gồm cửa sổ 5h và 7d, % đã dùng, giờ reset. Không đọc nội dung hội thoại.</li><li>Sandbox Windows của codex không thấy `python`: worker không tự chạy test được, engine verify bên ngoài.</li><li>Skill và rule toàn cục trong `~/.codex` cũng được nạp vào worker.</li></ul> |
| `agy` | Đã kiểm chứng:<ul><li>`-p` phải đứng ngay trước prompt.</li><li>Mỗi lời gọi tốn khoảng 16,6K token overhead, nên lead giao cho nó ít task nhưng lớn.</li><li>Kết quả JSON nằm trong `structured_output`.</li><li>Không chạy được lệnh shell ở chế độ headless. Trường `note` trong catalog báo trước điều này cho nó.</li></ul> |
| `claude` | Đã cài nhưng chưa đăng nhập, nên cờ chưa kiểm chứng. |
| `claude@zai` | Claude Code trỏ tới endpoint tương thích Anthropic của Z.ai. Cần `ZAI_API_KEY` trong vault. |
| `opencode` | Đã nâng lên 1.18.34; bản cũ tự lỗi khi migrate sqlite.<ul><li>Profile gốc dùng dữ liệu thật của bạn, nên discover nên tránh nó.</li><li>`opencode` lấy thư mục dự án từ biến `PWD`, không lấy cwd thật. `spawn()` luôn đặt `PWD` bằng cwd; trước khi sửa, pre-test đã ghi file ra ngoài worktree.</li></ul> |
| `opencode@free` | Model free của OpenCode Zen, không cần tài khoản.<ul><li>Chạy với `--pure` và thư mục dữ liệu riêng: `XDG_DATA_HOME=~/.orchestra/opencode-free`.</li><li>Danh sách model còn có `meta/*`, có thể cần đăng nhập; pre-test sẽ lọc ra.</li></ul> |
| `opencode@9router` | Provider tương thích OpenAI, cấu hình qua `OPENCODE_CONFIG_CONTENT`.<ul><li>Key đi từ vault qua biến `ROUTER_API_KEY`, không bao giờ nằm trong JSON cấu hình.</li><li>Header `X-9Router-Token-Saver: off`.</li><li>Model lấy từ `GET /v1/models` của router.</li><li>Mỗi tiền tố provider là một tài khoản. `shares` (`cx`→`codex`, `ag`→`agy`, `cc`→`claude`, `gc`→`gemini`, `cu`→`cursor-agent`) gộp các tiền tố trùng subscription với CLI (§6.1).</li><li>Mặc định `http://127.0.0.1:20128/v1`. Router chạy port khác thì ghi đè trong `~/.orchestra/agents.json`.</li></ul> |
| `gemini`, `cursor-agent` | Có manifest sẵn, chưa kiểm chứng. |
| `mock`, `mock@b`, `mock@c` | Ẩn. Agent theo kịch bản, dùng cho test. `@b` và `@c` là tài khoản thứ hai và thứ ba để test xoay vòng. |

Profile `agent@x` kế thừa `base` rồi ghi đè vài trường. Mỗi profile là một tài khoản riêng (một quota riêng), trừ profile router (§6.1).

`~/.orchestra/agents.json` ghi đè catalog theo từng profile và chỉ áp dụng trên máy này (ví dụ port của router). Catalog trong repo giữ nguyên.

Về tiến trình:
- Shim npm (`*.cmd`) được giải về binary thật, để tránh cmd.exe tự phân tích tham số.
- Mỗi agent chạy trong một Windows Job Object (kill-on-close), hoặc process group trên POSIX: engine chết thì cả cây tiến trình chết theo.
- Tiến trình con nhận `PWD` bằng chính cwd của nó.
- Hết timeout thì kill cả cây.
- Mỗi workspace chỉ có một engine (khoá file của OS).

## 9. Tối ưu context, token và thời gian

Xếp theo mức tác động (thống nhất với Codex ở vòng 1):

1. **Ít lời gọi hơn.**
   - Lead gom việc liên quan thành ít task.
   - Reviewer chỉ chạy ở 2 mốc: plan và review cuối.
   - Agent có overhead cao (agy) nhận task lớn hơn.
2. **Gửi tham chiếu, không gửi transcript.** Worker chỉ nhận:
   - task, acceptance, scope, verify của chính nó;
   - tóm tắt của các dependency (≤ 600 ký tự, ≤ 20 file, ≤ 8 facts mỗi dependency);
   - top-k facts liên quan.

   Worker không bao giờ nhận lịch sử hội thoại của agent khác.
3. **Handoff có giới hạn:** summary, files, decisions và tối đa 5 facts.
4. **Kiểm soát đầu ra công cụ.**
   - Repo map tối đa 300 dòng (150 cho reviewer). Repo lớn hơn thì gộp theo thư mục, kèm số file.
   - Lỗi verify chỉ giữ 3.000 ký tự cuối.
   - Log đầy đủ nằm trong `attempts/`, không nằm trong prompt.
5. **Tiền tố ổn định.** Rule và contract đứng đầu, phần thay đổi đứng cuối, để tận dụng prompt cache của provider.
6. **Resume có chủ đích.** Chỉ resume session khi sửa plan, repair JSON, hoặc thử lại cùng task (chỉ gửi phần chênh lệch). Session hỏng thì bỏ.
7. **Skill tiết lộ dần.** Packet chỉ liệt kê đường dẫn `SKILL.md`; agent đọc khi cần.
8. **Ngân sách.** `budget_tokens` kích hoạt cổng BUDGET. Báo cáo ghi token và chi phí theo agent/model.
9. **Song song.** Task không phụ thuộc nhau chạy cùng lúc. Mặc định mỗi CLI một worker, để song song trên nhiều subscription.

## 10. Kênh giao tiếp và bộ nhớ chung

**Kênh chung là bảng `events`.**
- Append-only, đã che secret.
- Các loại sự kiện: start, handoff, verify, conflict, integrated, review, pending_user …
- Xem bằng `orch log`, tab Events, hoặc qua webhook (`ORCH_NOTIFY_URL`, định dạng ntfy/Slack/Discord).

**Knowledge graph tối thiểu.** Codex khuyên chưa dùng Graphiti hay LightRAG ở giai đoạn này.
- `facts` (FTS5/BM25) chỉ nhận facts từ task **đã tích hợp**, và gắn với commit.
- `kg_search` gộp hai bảng xếp hạng bằng reciprocal rank fusion:
  - từ khoá: FTS5/BM25. FTS5 không stem và giữ dấu tiếng Việt, nên "parsing" không thấy "Parser", "dang nhap" không thấy "Đăng nhập";
  - vector: mặc định là trigram ký tự TF-IDF tính tại chỗ, bỏ dấu và chữ hoa, nên bắt được hai trường hợp trên mà không gửi gì ra ngoài.
- Tìm theo nghĩa là opt-in: `"embeddings": {"url", "model", "key", "min"}` trong `team.json` trỏ tới một endpoint `/embeddings` kiểu OpenAI (Ollama, LM Studio, OpenAI …). Khi đó vector lấy từ endpoint thay cho trigram.
  - Nội dung fact được gửi tới endpoint đó.
  - Vector lưu trong bảng `vectors`, khoá là sha256(model, fact), nên mỗi fact chỉ gửi một lần cho mỗi model. Workspace chỉ đọc (MCP server của agent) không lưu được, nên gửi lại ở lần sau.
  - Endpoint lỗi thì quay về trigram và ghi một dòng ra stderr; tìm kiếm không bao giờ hỏng vì endpoint.
- `links` nối task với file đã sửa, và task với dependency.
- Agent tra cứu: `python -m orch kg search "<từ khoá>"` và `kg links <node>`, hoặc qua MCP server (dưới đây).
- Bạn thêm fact: `orch kg add <entity> <fact>`.
- Engine tự chèn top-k facts vào packet.

**MCP server** (`python -m orch mcp`, [orch/mcp.py](orch/mcp.py)).
- Ba tool chỉ đọc: `board`, `kg_search`, `kg_links`. Mỗi lần gọi tool mở một kết nối `mode=ro` mới, nên luôn thấy board mới nhất.
- JSON-RPC 2.0 qua stdio, mỗi dòng một thông điệp; stdout chỉ chứa thông điệp giao thức.
- Bật cho agent trong run bằng `"mcp": true` trong `team.json`. Engine truyền server theo từng lời gọi, không ghi file cấu hình nào của CLI:
  - codex: `-c mcp_servers.orch={…}` (TOML inline). `codex mcp get` đọc đúng cấu hình này. Chưa chạy lời gọi thật vì tốn quota.
  - claude: `--mcp-config <json>`, thêm `mcp__orch` vào `--allowedTools`. Chưa kiểm chứng vì chưa đăng nhập.
  - opencode và các profile của nó: khoá `mcp` trong `OPENCODE_CONFIG_CONTENT`, gộp với cấu hình router. `opencode mcp list` báo `connected`, kể cả với `--pure`.
  - agy, gemini, cursor-agent: chưa có cách truyền theo lời gọi.
- Lệnh khởi động server ghi rõ `PYTHONPATH` và `ORCH_HOME`. Lý do: CLI chỉ đưa cho MCP server một môi trường tối thiểu, và trên Windows thiếu thư mục home thì `orch` không import được.

**Worker chạy từ xa** ([orch/remote.py](orch/remote.py)). Một máy khác (có CLI và login riêng) làm worker; engine, scope, verify và merge vẫn ở máy chính.
- Team khai báo `{"agent": "remote", "model": "codex:gpt-5.5"}`. Engine gọi profile `remote` như mọi CLI khác: `python -m orch remote proxy <agent>:<model>`, prompt qua stdin, kết quả dạng JSON của agy. Engine không cần biết worker ở xa.
- Proxy chụp worktree (cả thay đổi chưa commit, dùng một index riêng để không đụng index thật) thành commit không cha, đóng `git bundle`, ghi lease vào bảng `leases`, rồi chờ.
- Runner (`python -m orch remote run --url …`) nối vào web UI qua `ssh -R`, nhận lease, dựng repo tạm từ bundle, chạy CLI thật bằng `agents.run_agent` và gửi heartbeat mỗi `stale/6` giây; cuối cùng gửi patch nhị phân và kết quả.
- Proxy áp patch bằng `git apply` rồi in JSON. Engine verify và gộp như với worker local.
- Đây là chỗ cần lease/heartbeat (§14, vòng 2): runner im lặng quá `ORCH_REMOTE_STALE` giây thì lần thử lỗi và `route()` thử lại. Engine kill proxy (timeout, cancel) thì `finally` của proxy không chạy; `sweep()` dọn lease có proxy đã chết (PID + thời điểm tạo), và heartbeat của runner nhận `cancel`.
- Mỗi CLI ở xa là một tài khoản `remote/<agent>` khi xoay vòng quota. Worker từ xa không có MCP hay knowledge graph.

**Chế độ điều khiển** (`mcp --control`). Thêm tool `run`, `status`, `answer`, `resume`, `cancel`, `doctor` cho phiên Claude Code hoặc Codex của chính bạn: nó giao mục tiêu cho đội nhiều hãng, theo dõi và chuyển câu trả lời của bạn.
- Engine chạy nền với `--exit-on-wait` và thoát khi chỉ còn chờ bạn; `answer` và `cancel` khởi động lại nó. Một engine sắp dừng vẫn giữ khoá, nên `answer` chờ tới khi engine nhận câu trả lời hoặc thoát hẳn.
- `status` dặn agent gọi tool không tự trả lời thay bạn; duyệt plan cũng là cho phép lệnh verify trong đó.
- Agent trong run không bao giờ nhận `--control` (`agents.mcp_server`).

**Rule.**
- File chung: `.orch/rules/common.md`, `lead.md`, `reviewer.md`, `worker.md`, `skill_architect.md`.
- Thêm một file cho mỗi worker.
- Bạn sửa tự do; engine không ghi đè.

## 11. Cơ sở dữ liệu model

**Nguồn dữ liệu.** `orch models refresh` tải về:
- **Epoch AI** `benchmark_data.zip` (CC-BY): ECI, SWE-bench Verified, Terminal-Bench, WebDev Arena, GPQA Diamond, HLE, METR time horizon;
- **OpenRouter** `/models`: context và giá.

Kết quả ghi vào `~/.orchestra/models.json` (bản cũ ghi ở `orch/catalog/models.json` vẫn được đọc). File này chưa có cho đến khi bạn chạy lệnh.

**Tách bạch bốn lớp** theo khuyến nghị của Codex:
- **model:** benchmark;
- **route:** CLI nào chạy được model đó;
- **quyền dùng:** xác nhận bằng probe;
- **quan sát:** `history.db`, ghi ok, thời gian, token, chi phí của từng lời gọi.

Giá OpenRouter chỉ là "giá API tham khảo", không áp cho CLI dùng subscription.

**Sử dụng.**
- `card()` tóm tắt mỗi model thành một dòng gọn cho prompt; lead đọc thẻ này thay vì lên web.
- `suggest()` gợi ý đội hình theo chất lượng kỳ vọng `(k·prior + đúng) / (k + đúng + sai)`, với k = 5:
  - prior là percentile năng lực benchmark của model (0,5 nếu không có kết quả công khai);
  - đúng = lời gọi kết thúc `ok` hoặc `integrated`; sai = `verify`, `invalid`, `timeout`. Hết quota hay lỗi auth không nói gì về model nên không tính;
  - lead là cặp có điểm cao nhất; reviewer thuộc tổ chức khác với lead;
  - mỗi tài khoản (`agents.account`) một worker, tối đa 4 worker.

## 12. Skill architect

**Nguồn curated, ghim commit:**
- `anthropics/skills` và `openai/skills` ([orch/catalog/skills.json](orch/catalog/skills.json));
- thư mục skill local: `~/.claude/skills`, `~/.codex/skills`, `~/.agents/skills`.

`orch skills refresh` lập chỉ mục mọi `SKILL.md`. Lệnh này cần Internet và do bạn tự chạy.

**Trong mỗi run**, task SKILLS chọn tối đa 3 skill thật sự giúp được task cụ thể ("không có còn hơn chọn skill tầm thường"). Với mỗi skill được chọn:
1. Tải đúng commit đã ghim.
2. Tính sha256.
3. Quét tĩnh: liệt kê script và các mẫu đáng xem như `curl`, `rm -rf`, `eval(`.
4. Copy vào `<worktree>/.agents/skills/orch-<tên>/` của đúng task. Theo tài liệu của Codex, nó tự nhận thư mục này. Mọi CLI, kể cả codex, đều được chỉ đường dẫn `SKILL.md` trong packet.

**Repo ngoài danh sách** chỉ được đề xuất. Bạn quyết bằng `orch skills approve|reject <url>`. Repo được duyệt sẽ vào nguồn của bạn và được ghim commit ở lần refresh sau.

**Tắt hẳn** bằng `"skills": false` trong `team.json`.

## 13. Bảo mật và quyền hạn

Ma trận quyền:

| Lead tự quyết | Chỉ bạn quyết |
|---|---|
| <ul><li>Thử lại, giao lại, huỷ task.</li><li>Lập lại plan.</li><li>Bổ sung task sau review cuối (tối đa `max_amend`).</li></ul> | <ul><li>Secret và đăng nhập.</li><li>Đổi mục tiêu hoặc cắt phạm vi.</li><li>Vượt ngân sách.</li><li>Cài skill ngoài danh sách.</li><li>Merge vào nhánh của bạn.</li><li>Thao tác phá huỷ.</li><li>Duyệt plan (trừ khi bật `auto_approve`).</li></ul> |

**Vault.**
- Trên Windows: DPAPI phạm vi người dùng, tại `~/.orchestra/vault.dpapi`. Ngoài Windows: JSON chmod 600.
- DPAPI bảo vệ file khi nằm yên trên đĩa, nhưng không giấu được secret khỏi code chạy dưới chính tài khoản của bạn.

**Môi trường tối thiểu.**
- Mọi biến môi trường trông giống secret đều bị loại: tên chứa `KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL`, `AUTH` (cả `SSH_AUTH_SOCK`), `COOKIE`, `DSN`, đuôi `_PAT`; và giá trị là URL có `user:password@` (ví dụ `DATABASE_URL`).
- Mỗi agent chỉ nhận lại đúng các biến chứng thực mà adapter của nó khai báo.
- Lệnh verify chạy code do worker viết, nên dùng danh sách cho phép thay cho danh sách cấm: biến hệ thống, locale, thư mục tạm và toolchain (`PYTHON*`, `NODE_*`, `GOPATH`, `JAVA_HOME` …). `team.json` `"verify_env"` thêm tên; tên trông giống secret vẫn bị loại.
- Secret bị che trong events, log và UI.

**Git.**
- Engine commit với hook bị tắt, không ký, không prompt.
- Không bao giờ ghi vào nhánh hay working tree của bạn.
- `.orch/` và `.agents/skills/orch-*/` nằm trong `info/exclude`.

**Web UI.**
- Chỉ bind 127.0.0.1.
- Mỗi lần mở có một token ngẫu nhiên. Token nằm trong fragment của URL (không bao giờ gửi lên server hay ghi log) và được gửi qua header `X-Orch-Token`.
- Kiểm tra Host để chống DNS rebinding, kiểm tra Origin để chống CSRF.
- CSP với nonce; dữ liệu render bằng text node, không dùng `innerHTML`. Sơ đồ DAG cũng vậy: SVG dựng bằng DOM, chữ là text node.
- Giới hạn kích thước request và timeout socket.
- Vault chỉ hiện ở dạng đã che.
- Server từ chối câu trả lời rỗng: không bao giờ coi rỗng là `yes`.
- Route của runner từ xa (`/api/lease*`) chỉ nhận `ORCH_REMOTE_TOKEN` (từ 16 ký tự), token này không mở route nào khác, và token của UI không mở route của runner. Ai có token remote và vào được port của UI thì đọc được mã nguồn (bundle) và prompt, nên chỉ nối qua 127.0.0.1 hoặc đường hầm SSH.
- Bản sửa plan (`POST /api/plan`) chỉ đổi dependency và worker. Engine kiểm tra lại như plan của lead (§4), nên UI không thể đưa vào plan một worker lạ hay một chu trình.

**Router local (9router và tương tự).** Prototype chỉ là client; việc cài đặt và đăng nhập do bạn làm.
- Mặc định của 9router không an toàn: `REQUIRE_API_KEY=false`, `INITIAL_PASSWORD=123456`, Docker bind `0.0.0.0`, có Cloud Sync và các tính năng MITM.
- Khuyến nghị: `HOSTNAME=127.0.0.1`, `REQUIRE_API_KEY=true`, đổi mật khẩu, tắt Cloud Sync. Không bật MITM, cài chứng chỉ hay DNS.
- Key nằm trong vault. Engine chỉ đưa key vào biến môi trường của đúng profile, không bao giờ ghi vào file cấu hình.

**Quota.** Từ rollout của codex, engine chỉ đọc object `rate_limits` và thời điểm ghi, không đọc nội dung hội thoại.

**Điều khoản của nhà cung cấp.** Xoay vòng tài khoản lập lịch trên các tài khoản và key người dùng sở hữu hợp lệ; nó không phải công cụ lách hạn mức. Nhiều nhà cung cấp cấm chia sẻ tài khoản, mở nhiều tài khoản để vượt hạn mức, hoặc dùng gói thuê bao cá nhân qua công cụ bên thứ ba. README ghi rõ điều này, và ghi 9router là tự chịu rủi ro. Dùng chung, trên máy chủ hay trong CI thì dùng API key.

**GitHub Action.**
- Input đi vào `run.py` qua biến môi trường, không bao giờ chèn vào dòng lệnh shell (chống script injection).
- `goal` là prompt cho agent đang giữ API key: chỉ kích hoạt bằng `workflow_dispatch` hoặc label do maintainer gắn, không nối nội dung issue/comment của người lạ.
- Run trong CI tự duyệt plan (không có ai để hỏi), nên nên đặt `verify_allow`. Lệnh verify vẫn chạy với danh sách biến môi trường cho phép, nên không thấy API key.

**Worktree không phải sandbox.** Agent chạy với quyền của bạn.
- Giới hạn thật duy nhất là sandbox/permission mode của từng CLI (`codex -s workspace-write`, `claude --permission-mode acceptEdits` …).
- Kiểm tra phạm vi diễn ra **sau** khi agent làm xong (từ chối diff), không ngăn được trước.

### ⚠ Hai điểm va chạm với `AGENTS.md` ở thư mục cha

`AGENTS.md` là quy tắc của dự án Codex, trong đó có: "never run commands from model JSON, install remote skills automatically …".

1. **Lệnh verify đến từ plan JSON của lead.** Hiện tại reviewer xem các lệnh này, bạn duyệt chúng trong `plan.md` (trừ khi dùng `--yes`/`auto_approve`), rồi engine chạy chúng không qua shell, không có secret, có timeout. Lệnh mới trong bản amend (lead viết sau review cuối, sau khi bạn duyệt) bị hỏi riêng trước lời gọi worker, kể cả khi không đặt `verify_allow`; chỉ run `auto_approve` mới tin lead ở bước này. Các lựa chọn:
   - (a) Giữ nguyên, nhưng cấm `auto_approve`.
   - (b) Thêm danh sách lệnh được phép trong `team.json`, ví dụ `["python", "-m", "unittest"]`; lệnh ngoài danh sách thì hỏi bạn.
   - (c) Chỉ dùng lệnh verify do bạn định nghĩa.
2. **Skill curated được tải tự động trong run**, dù đã ghim commit, có sha256 và quét tĩnh. Các lựa chọn:
   - Đặt `"skills": false`.
   - Hoặc chuyển mọi skill sang trạng thái "đề xuất, chờ bạn duyệt".

Prototype đã có cơ chế opt-in cho cả hai điểm. Mặc định giữ hành vi cũ, vì bật hay không là quyết định của bạn.
- `"verify_allow": [["python", "-m", "unittest"], …]` (lựa chọn b). Mỗi phần tử là một tiền tố lệnh.
  - Lệnh ngoài danh sách dừng task **trước** khi gọi worker, kể cả khi `auto_approve`.
  - Bạn trả lời `yes` một lần thì lệnh đó được phép trong cả run, và mọi task đang chờ vì cùng lệnh được thả.
  - Duyệt plan bằng tay cũng là duyệt các lệnh trong plan đó. `plan.md` ghi `(not in verify_allow)` cạnh từng lệnh ngoài danh sách. Lệnh trong bản amend chưa ai xem nên vẫn bị hỏi.
- `"skills": "propose"`. Skill curated được chọn chỉ ở trạng thái đề xuất.
  - Task SKILLS hỏi bạn một lần; các task work chờ câu trả lời.
  - `yes` thì cài tất cả; câu trả lời khác thì làm tiếp mà không có skill.

## 14. Trao đổi với Codex (2 vòng)

Biên bản đầy đủ, theo thứ tự:
1. [round1_prompt.md](docs/codex/round1_prompt.md)
2. [round1_reply.md](docs/codex/round1_reply.md)
3. [round2_prompt.md](docs/codex/round2_prompt.md)
4. [round2_reply.md](docs/codex/round2_reply.md)

Log sự kiện `*_events.jsonl` nằm cùng thư mục.

### Vòng 1: Claude gửi bản nháp kiến trúc, Codex phản biện

Năm điểm yếu lớn nhất Codex chỉ ra:
1. **Scheduler thiếu ngữ nghĩa khi crash.** Cần tách task với attempt, có bước khôi phục, ghi "ý định merge" và commit.
2. **Cô lập credential bị nói quá.** Cần DPAPI và danh sách biến môi trường được phép. Worktree không phải ranh giới bảo mật.
3. **"Done" đang trộn sinh code, kiểm chứng và tích hợp.** Engine phải tự quan sát diff, scope, test, commit id; task phụ thuộc phải chạy từ commit đã tích hợp.
4. **Adapter chỉ-JSON và zero-dependency là tiết kiệm giả.** Cần hook tiến trình riêng cho từng CLI.
5. **Plan và retry quá cứng.** Cần kiểm tra DAG trước khi duyệt, không âm thầm chấp nhận blocker, và phân loại lỗi.

Codex còn đưa ra:
- cờ Codex CLI cho worker chạy không giám sát;
- bảng xếp hạng kỹ thuật tiết kiệm token;
- knowledge graph tối thiểu = SQLite + FTS5;
- quy trình an toàn cho skill;
- cách tách model / route / quyền dùng / quan sát;
- phạm vi MVP.

### Vòng 2: Claude kiểm chứng trên máy rồi chốt

Kiểm chứng trên máy:
- cờ resume của codex;
- model bị từ chối tuỳ loại tài khoản;
- overhead của agy;
- claude chưa đăng nhập, opencode bị lỗi;
- shim npm.

**Chấp nhận từ Codex và đã hiện thực:**
- Bảng attempts và bước reconcile; kill cây tiến trình mồ côi.
- Vòng đời: engine quan sát diff → scope → verify → commit → nhánh tích hợp riêng.
- Phân loại lỗi:
  - auth → hỏi người dùng;
  - rate limit → backoff;
  - còn lại → lead triage;
  - không lặp y hệt quá một lần.
- Kiểm tra DAG trước khi duyệt; còn blocker sau 2 vòng thì hỏi người dùng; đánh version cho plan khi amend.
- Ma trận quyền, giới hạn song song, ngân sách token, huỷ theo cây tiến trình, không đụng working tree đang dở của người dùng.
- Facts chỉ đến từ task đã tích hợp; FTS5 + links.
- Skill: ghim commit, sha256, quét tĩnh, duyệt.
- UI: token, kiểm tra Host/Origin, chỉ bind 127.0.0.1, render an toàn.
- Lead stateless.

**Ba điểm Claude giữ quan điểm, và Codex trả lời:**

| Claude giữ | Codex trả lời | Kết quả |
|---|---|---|
| (a) Vẫn zero-dependency: DPAPI qua ctypes, `http.server` có token, validator nhỏ | Chấp nhận, kèm điều kiện: kiểm tra chặt 3 contract; từ chối key trùng, NaN, payload lớn; giới hạn request và timeout | Đã làm |
| (b) Không dùng lease/heartbeat, vì một engine sở hữu mọi tiến trình con | Đồng ý bỏ lease, nhưng chỉ dựa vào PID là chưa đủ | Đã làm: PID + thời điểm tạo, Job Object, khoá OS cho một engine |
| (c) Giữ UI, vault, login, model DB, skill trong MVP vì người dùng yêu cầu | Chấp nhận. Chọn model thủ công; skill là bản ghi có thể duyệt; adapter lỗi vẫn hiển thị kèm lý do | Đã làm |

**Codex còn sửa máy trạng thái:**
- Không dùng trạng thái `failed` tạm thời.
- `needs_lead` và `pending_user` phải có cạnh chuyển rõ ràng.
- Khôi phục `integrating` dựa trên **đúng commit đã ghi**.
- `done` cần bằng chứng tích hợp và verify.
- Review cuối kiểm lại cây tổng.
- Hoàn tất run khác với merge vào nhánh người dùng.

Codex cũng đề xuất 3 test đầu tiên: crash khi đang tích hợp, handoff không đáng tin, nhánh bị chặn trong khi nhánh anh em vẫn chạy. Cả ba đều đã có trong bộ test (§15).

## 15. Kiểm thử

Chạy bằng `python tests/test_e2e.py [lọc-tên]`.
- Test chạy engine thật với mock agent theo kịch bản.
- Mỗi test dùng một repo git tạm: tự xoá khi pass, giữ lại khi fail để điều tra.
- `ORCH_HOME` trỏ vào một thư mục tạm, nên test không đụng `~/.orchestra` thật.
- Thời gian: Linux khoảng 50 giây, Windows khoảng 2–3 phút.

| Test | Chứng minh |
|---|---|
| `happy_path` | <ul><li>Plan → 2 task phụ thuộc nhau → tích hợp → review → done.</li><li>File bị `.gitignore` có trong worktree lúc verify thì có cảnh báo, và không vào commit.</li><li>Nhánh của bạn không bị đụng tới.</li><li>Facts đến được task phụ thuộc.</li><li>Tìm được trong KG; lệnh verify hiển thị có quote.</li></ul> |
| `crash_during_integration` | <ul><li>Crash sau merge, trước khi DB ghi xong.</li><li>Resume tích hợp đúng một lần; task phụ thuộc chạy đúng một lần.</li><li>Bằng chứng được giữ lại.</li></ul> |
| `untrustworthy_completion` | <ul><li>Handoff báo "done" nhưng sửa ngoài scope, rồi verify thất bại.</li><li>Kết quả: không merge, không ghi facts, không chạy task phụ thuộc.</li><li>File bị từ chối không lọt vào lịch sử git.</li></ul> |
| `blocked_branch_live_sibling` | <ul><li>Một worker lỗi auth và chờ bạn; nhánh kia vẫn hoàn thành.</li><li>Trả lời `retry` thì chạy lại đúng một lần.</li></ul> |
| `malformed_handoff_is_repaired` | <ul><li>Worker trả lời không phải JSON.</li><li>Engine repair một lần qua session cũ.</li></ul> |
| `timeout_then_lead_reassigns` | <ul><li>Agent treo bị kill khi hết timeout.</li><li>Lead triage và giao cho worker khác.</li><li>Patch bằng chứng của lần thử bị bỏ là byte nguyên bản của git, `git apply --check` được.</li></ul> |
| `usage_limit_rotates_and_switches_back` | <ul><li>Worker hết usage giữa task, backup làm tiếp ngay trong worktree đó.</li><li>Tới giờ reset, task quay về worker chính.</li><li>Vai trò hết usage có người đứng thay.</li></ul> |
| `pre_rotation_skips_an_exhausted_worker` | Task đang xếp hàng sau một tài khoản vừa hết usage được chuyển sang backup trước khi chạy. Không có ghi chú "phần việc dở". |
| `quota_outlook_from_codex_rollouts` | <ul><li>Đọc `rate_limits` từ rollout giả.</li><li>Tính % đã dùng, tốc độ dùng, dự báo "hết lúc ~", trạng thái at risk.</li><li>Bản ghi 100% thì khoá tới giờ reset.</li></ul> |
| `router_profile_lists_models_and_routes_opencode` | <ul><li>Router giả: danh sách model, key gửi qua header Bearer, key không lọt vào cấu hình.</li><li>Có opencode thì thêm một lời gọi thật qua router giả.</li><li>Tiến trình con nhận `PWD` bằng cwd.</li></ul> |
| `router_accounts_per_provider_and_shared` | <ul><li>`~/.orchestra/agents.json` ghi đè profile trên máy này.</li><li>Router: mỗi tiền tố provider một tài khoản. Tiền tố trong `shares` hết usage cùng CLI, nên backup trên tiền tố đó bị bỏ qua.</li></ul> |
| `account_limits_parallelism_and_risk_lowers_rank` | <ul><li>`account_max` bắt hai worker cùng tài khoản chạy lần lượt.</li><li>Tài khoản at risk xếp sau trong pool.</li></ul> |
| `suggest_shrinks_benchmarks_toward_history` | <ul><li>Prior benchmark co về lịch sử: model mạnh mà hay báo "done" sai mất vị trí lead.</li><li>Lỗi quota không tính; mỗi tài khoản một worker.</li></ul> |
| `pool_plan_ranks_pretests_and_backs_up` | <ul><li>`pool plan` xếp hạng và pre-test. Preset `precise` dùng bài khó, `pool test` mặc định dùng bài dễ.</li><li>Model báo "done" mà kiểm tra trượt bị ghi `verify` và xếp sau.</li><li>Lưu backup riêng cho từng worker.</li><li>Trong run, backup đó thật sự nhận task khi worker chính hết usage.</li></ul> |
| `merge_conflict_is_resolved_by_the_worker` | <ul><li>Hai task sửa cùng một file.</li><li>Worker đến sau nhận dấu xung đột, tự gộp, rồi được tích hợp.</li></ul> |
| `plan_review_user_approval_and_amendment` | <ul><li>Reviewer chặn → lead sửa plan bằng session cũ.</li><li>Bạn duyệt.</li><li>Review cuối chặn → amend → REVIEW2.</li><li>Lệnh verify mới trong bản amend dừng task trước lời gọi worker và hỏi bạn (lệnh đã duyệt trong plan thì không).</li></ul> |
| `budget_gate_then_stop` | <ul><li>Chạm ngân sách → cổng BUDGET.</li><li>`stop` huỷ run; task còn lại không chạy.</li></ul> |
| `skill_architect_installs_and_places` | <ul><li>Cài skill, quét ra script đáng xem.</li><li>Đặt đúng worktree của task, không commit skill.</li><li>Repo ngoài danh sách thành đề xuất và được `approve`.</li></ul> |
| `opt_in_gates_verify_allowlist_and_skill_proposals` | <ul><li>`skills: propose`: skill chờ bạn duyệt, task work chờ theo.</li><li>`verify_allow`: lệnh ngoài danh sách dừng task trước lời gọi worker, kể cả trong run auto-approve. Một `yes` thả mọi task chờ cùng lệnh.</li></ul> |
| `skills_index_offline` | <ul><li>Lập chỉ mục từ cây GitHub (giả lập mạng).</li><li>Cài đặt dùng lại cache theo commit.</li></ul> |
| `ui_server_security` | Token, Host, Origin, CSP; vault được che; kiểm tra input; câu trả lời rỗng bị từ chối. |
| `plan_edit_from_the_ui` | <ul><li>Sửa dependency và worker của plan đang chờ duyệt qua `POST /api/plan`, lưu thành v2.</li><li>Từ chối chu trình, worker lạ, bản sửa thiếu task, phiên bản cũ, và khi đã có câu trả lời.</li><li>Một `yes` đọc trước bản sửa không hiện thực hoá v1. Run chạy theo bản sửa.</li></ul> |
| `mcp_server_read_only_tools` | <ul><li>Với `"mcp": true`, agent của T2 tự khởi động server từ cấu hình được truyền, trong môi trường tối thiểu, và tìm thấy fact mà T1 công bố.</li><li>Giao thức: echo phiên bản, notification không được trả lời, chỉ có tool chỉ đọc, các mã lỗi JSON-RPC.</li><li>Lệnh gọi codex, claude, opencode khi bật và khi tắt MCP.</li></ul> |
| `kg_search_vectors` | <ul><li>FTS5 bỏ sót "parsing brackets" và "dang nhap"; trigram tìm ra.</li><li>Endpoint embeddings giả: tìm theo nghĩa, key trong vault đi qua header Bearer, kết quả trả về lộn thứ tự vẫn khớp.</li><li>Mỗi fact chỉ gửi một lần; workspace chỉ đọc vẫn tìm được, không lưu.</li><li>Endpoint chết thì quay về trigram, có thông báo.</li></ul> |
| `remote_worker` | <ul><li>Runner "ma" nhận lease rồi im lặng: proxy bỏ cuộc sau `ORCH_REMOTE_STALE`, lần thử ghi `error`, heartbeat nhận `cancel`, kết quả muộn bị từ chối.</li><li>Token UI không mở route runner và ngược lại.</li><li>Lần thử lại được một tiến trình `remote run` thật phục vụ; patch qua scope và verify rồi được tích hợp.</li><li>Không còn lease hay file lease nào.</li></ul> |
| `cli_parsers_failure_classes_and_env` | <ul><li>Parser agy, claude, opencode chạy trên đầu ra thật trong `docs/probes/`; parser codex trên sự kiện mẫu.</li><li>Lớp lỗi: các thông báo thật được nhận đúng; chữ của dự án (`/login`, "line 429", `quota.py`, `authenticate`) không bị coi là lỗi tài khoản, kể cả qua `run_agent`.</li><li>Môi trường: agent mất `SSH_AUTH_SOCK`, `DATABASE_URL` có mật khẩu, `*_PAT`; lệnh verify chỉ nhận danh sách cho phép, `verify_env` thêm tên nhưng không thêm secret.</li></ul> |
| `mcp_control_drives_a_run` | <ul><li>Qua MCP `--control`: `doctor`, `run`, chờ plan, `answer` rỗng bị từ chối, `run` thứ hai bị từ chối khi run cũ còn mở, `answer yes` khởi động lại engine, run xong và `status` trả về báo cáo.</li><li>Server không có `--control` chỉ có tool chỉ đọc; agent trong run không nhận `--control`.</li></ul> |
| `github_action_runs_and_opens_a_pull_request` | <ul><li>`action/run.py` với team từ file, run tự duyệt, output và tóm tắt của job.</li><li>Nhánh `orctram/<run>` được đẩy lên một remote bare, `gh` giả nhận đúng tham số tạo PR (Windows dừng trước bước PR).</li><li>Input đi vào script qua biến môi trường, không chèn vào dòng lệnh shell.</li></ul> |
| `bench_solo_versus_team` | Agent làm một mình viết sai `add()` nên trượt check; cả đội qua check. Báo cáo có số lời gọi, câu hỏi, nhánh kết quả; không còn worktree thừa; thiếu `--check` thì từ chối. |
| `doctor` | Máy, dự án, team, DB, engine; agent của team chưa cài hoặc token remote quá ngắn thì mã thoát 1; không in secret. |
| `db_schema_versions` | DB trước khi có phiên bản lên version 1 và có đủ bảng; migration chạy đúng một lần; DB của bản Orctram mới hơn bị từ chối. |
| `package_ships_its_data` | Mọi file dữ liệu trong `orch/` (catalog, `ui.html`) nằm trong package data; lệnh `orctram`, version và LICENSE đúng; không có dependency. |
| `scope_and_plan_checks` | Các kiểm tra plan, scope, allowlist lệnh verify và repo map ở dạng hàm thuần. |

## 16. Lộ trình

**P0: ngay sau đây (cần bạn đồng ý hoặc thao tác)**
1. `python -m orch models refresh` và `python -m orch skills refresh` (tải từ Internet).
2. `python -m orch login claude` (gõ `/login` trong cửa sổ mở ra) để dùng được Claude Code, rồi kiểm chứng các cờ của nó.
3. ~~Smoke run thật với đội codex + agy~~: đã xong (§0).
4. Quyết định hai điểm va chạm ở §13. Cơ chế opt-in đã có, chỉ cần bật trong `team.json`.
5. Dùng 9router: cấu hình an toàn (§13), `vault set NINEROUTER_API_KEY`, rồi `discover --only opencode@9router --probe` và `pool plan`. Router chạy port khác 20128 thì ghi đè trong `~/.orchestra/agents.json`.

**P1: đã xong (2026-10-03)**
- Ranking trừ điểm tài khoản at risk (§6.1).
- Pre-test khó cho `match` và `precise` (§6.1).
- Opt-in allowlist lệnh verify và chế độ duyệt skill (§13).
- `suggest()` co benchmark prior về lịch sử chạy thật (§11).
- Giới hạn song song theo tài khoản bằng `account_max` (§6.1).
- Repo map gộp theo thư mục cho repo lớn (§9).

**P2**
- Canvas DAG kiểu n8n: đã có.
  - Tab Run có sơ đồ: mỗi cột một độ sâu phụ thuộc, màu theo trạng thái, nét đứt là thứ tự ngầm (work chạy sau PLAN và SKILLS).
  - Plan đang chờ duyệt sửa được bằng kéo-thả (§4, bước 4).
- Embeddings cho knowledge graph: đã có (§10). Trigram tại chỗ mặc định; endpoint embeddings là opt-in.
- MCP server cho board và knowledge graph: đã có (§10).
- Worker chạy từ xa: đã có (§10), kèm lease và heartbeat. Còn phải chạy thử với CLI thật qua đường hầm SSH.
- Thiết kế lại giao diện web UI: pha 1–3 xong và đã QA trên Chromium; pha 4 đã có toast vừa màn 360px và cuộn theo `prefers-reduced-motion`, còn audit theo bộ quy tắc ghim, thử Narrator và ảnh chụp README ([docs/UIUX.md](docs/UIUX.md) §12).

**P3: thành sản phẩm, hướng A (công cụ local mã nguồn mở) và E (làm công cụ cho agent khác), 2026-10-05**
- Đã xong:
  - tên Orctram (lần lượt thay Orchestra và Hoatau), license Apache-2.0, version 0.1.0;
  - đóng gói `pyproject.toml`, lệnh `orctram`; catalog nằm trong gói; dữ liệu tải về ở `~/.orchestra`;
  - migration SQLite theo `PRAGMA user_version`;
  - `doctor`;
  - CI GitHub Actions (Windows, Linux, macOS không chặn; wheel; Action);
  - MCP `--control`;
  - GitHub Action (beta);
  - workflow phát hành `release.yml`: tag `vX.Y.Z` → test, sdist + wheel, PyPI qua Trusted Publishing, GitHub Release;
  - `bench`: cùng mục tiêu, một agent làm một mình và cả đội, chấm bằng lệnh `--check` của bạn;
  - UI pha 4: audit bằng script (tên dễ hiểu, nhãn, landmark, thứ tự heading, vùng bấm 24px), ảnh chụp README.
- Việc của bạn:
  - trên PyPI: thêm trusted publisher (repo này, `release.yml`, environment `pypi`), rồi push tag `v0.1.0`;
  - chạy `orctram bench` trên vài việc thật của bạn với agent thật: đây là bằng chứng sản phẩm đáng dùng hay không;
  - chạy thử Action với agent thật và API key; thử Narrator.
- Tiếp theo nên làm:
  - adapter qua giao thức chuẩn (Agent Client Protocol, SDK của từng hãng) thay cho đọc output CLI;
  - tuỳ chọn chạy worker và verify trong container;
  - tách `engine.py`;
  - `bench --repeat` và bảng tổng hợp nhiều lần chạy.

**Sửa sau đợt review 2026-10-04**
- Lớp lỗi chỉ lấy từ lỗi của CLI và stderr (§6).
- Lệnh verify của bản amend được hỏi khi không đặt `verify_allow` (§13).
- Lệnh verify chạy với danh sách biến môi trường cho phép; agent mất thêm `SSH_AUTH_SOCK`, `*_PAT`, URL có mật khẩu (§13).
- Cảnh báo khi verify chạy cùng file bị `.gitignore` mà commit không mang theo: verify ở worktree thấy chúng, review cuối chạy lại verify trên nhánh tích hợp thì không.
- File văn bản ghi LF; patch bằng chứng ghi đúng byte của git.

**Giới hạn đã biết** (đánh dấu `ponytail:` trong code):
- Repo map cắt ở cùng một độ sâu thư mục cho cả cây (tối đa 300 dòng).
- Sơ đồ DAG xếp hàng theo thứ tự board, chưa giảm cạnh cắt nhau; cạnh nhảy cột có thể chạy sau node ở giữa.
- Gợi ý đội hình: prior cố định nặng bằng k = 5 lời gọi; chưa tính thời gian và token.
- Tài khoản at risk bị nhân hệ số cố định 0,75, không theo thời gian còn lại trước khi hết.
- Knowledge graph so vector bằng brute force, tính lại tần suất trigram ở mỗi lần tìm: ổn dưới khoảng 10k fact. Endpoint embeddings treo thì mỗi lần tìm chờ tối đa 30 giây (chưa nhớ lỗi).
- Chỉ mục skill bị cắt nếu cây repo có hơn 100k mục.
- Worker từ xa: mọi runner của một CLI tính chung một tài khoản; bundle chở cả cây mỗi lần thử (chưa gửi phần chênh lệch); không có MCP hay knowledge graph.
- Verify chạy trong worktree của worker, nên thấy cả file bị `.gitignore` mà commit không mang theo (có cảnh báo; review cuối chạy lại trên nhánh tích hợp). Verify trên một checkout sạch sẽ chặn sớm hơn, nhưng làm hỏng dự án cần thư mục phụ thuộc cục bộ như `node_modules`.
- Một engine mỗi workspace.
- Ưu tiên Windows (DPAPI, Job Object). Nhánh POSIX đã qua bộ test trên Linux/WSL, nhưng chưa chạy với agent thật.
- Dự báo "hết lúc ~" dùng tốc độ dùng của giờ gần nhất, nên bi quan sau một đợt dùng dày.
- Task chỉ quay về worker chính ở ranh giới lần thử, không cắt ngang lời gọi backup đang chạy.
- Bộ đếm của mock agent không khoá: hai lời gọi song song cùng `role:task` có thể dùng chung một bước kịch bản.

## 17. Quan hệ với bộ đề xuất của Codex ở thư mục cha

Thư mục cha có:
- bộ tài liệu đề xuất do Codex viết: [../README.md](../README.md), [../docs/](../docs/);
- kênh nghiên cứu Codex ↔ Gemini.

Prototype này độc lập và không sửa file nào ở đó. Khi hợp nhất, nên đối chiếu các phần cùng chủ đề:

| Tài liệu Codex | Prototype |
|---|---|
| `docs/ARCHITECTURE.md` §4 "Vòng đời một nhiệm vụ", §5 "DAG, lỗi và chờ người dùng" | §4–6 ở đây |
| `docs/ARCHITECTURE.md` §11 "Trust boundary và quyền thực thi" | §13 |
| `docs/ROADMAP.md`, giai đoạn 1–4 | Phần đã có trong prototype |
