# Kênh Codex ↔ Gemini qua Antigravity

User đã yêu cầu tạo kênh local và gọi Gemini làm nghiên cứu. Quyền mới này cho phép
lead gọi một worker Gemini; không tự authorize worker gọi model khác, implement
sản phẩm, cài plugin, đọc secret hoặc chạy các experiment runtime.

## Cách trao đổi đang dùng

`scripts/research_channel.py` là bridge riêng cho **G00 revision 1**, dùng Python
stdlib và Antigravity có sẵn; không tích hợp vào app nháp. Hỗ trợ revision 1 và
hai correction revisions (2–3) khi có independent REVISE gắn đúng prior result hash.

Model hiện tại theo lựa chọn user: **gemini-3.8-flash-high**. Lượt Pro trước đó
đã dừng khi user đổi model; usage/billing của lượt bị hủy chưa có terminal telemetry.

1. Lead đóng gói các input G00 với path/hash actual. Không đưa credentials vào packet.
2. Bridge tạo workspace riêng và agent research-bridge. Không chỉnh settings global.
3. CLI nhận NDJSON user message qua stdin; trả init/step_update/result qua stdout.
   Tool finish được phép chỉ cho lifecycle/bàn giao nếu CLI yêu cầu; không tool domain khác.
4. Bridge kiểm model/agent/request-review trước khi gửi task; không skip permissions.
5. Gemini trả report_markdown và task_result có schema. Host chỉ ghi hai output
   G00 cố định sau structural/schema validation; không execute nội dung model.
6. Codex/lead review evidence riêng, ghi reviews/G00.json. Không tự chạy G01.

Protocol theo [headless docs](https://antigravity.google/docs/cli/headless/).
Agent file theo [custom agents docs](https://antigravity.google/docs/subagents/).
Plan mode theo [execution modes](https://antigravity.google/docs/cli/modes/).

## Trạng thái, inbox/outbox và dữ liệu theo dõi

Root runtime: `D:\Hierarchical-Multi-Agent\.orchestra\research-channel\` (gitignored).

- `latest.json`: pointer tới run gần nhất.
- `runs/<id>/input-packet.json`: inputs actual và hashes.
- `request.json`: inbox một task lead đã giao.
- `output.schema.json`: contract trả về.
- `init-observed.json`: cấu hình init thực CLI công bố.
- `events.ndjson`: lifecycle/usage metadata; bỏ text reasoning và tool payloads.
- `diagnostics.log`: stderr qua redaction cơ bản; không đảm bảo lọc mọi secret pattern.
- `response.json`: outbox envelope thực của CLI.
- `candidate.json`: report/result trả về, chưa independent acceptance.
- `status.json`: PREPARED/STARTING/RUNNING/PENDING_REVIEW/WAITING_INPUT/
  BLOCKED_PREFLIGHT/COMPLETION_UNKNOWN/OUTPUT_REJECTED.

Usage lấy từ vendor result; cumulative session counters, không báo USD khi chưa
có price/entitlement evidence. Conversation ID là correlation cho review/followup,
không proof account identity/quota.

## Giới hạn quyền thực và điều đã quan sát

Hai preflight đầu đã dừng **trước khi gửi task**: init của agy 1.2.14 công bố bộ
tools đầy đủ dù custom agent khai tools: []. Không kết luận tools đã bị disable
hoặc xác định nguyên nhân chỉ từ init. Bridge hiện yêu cầu plan/request-review,
prompt chỉ xử lý embedded packet và abort khi stream có tool event ngoài finish.

Đây là monitoring sau sự kiện, không interceptor có thể ngăn mọi tool trước khi
thực thi. Workspace/CWD và plan instruction không OS sandbox. Không dùng bridge
này cho untrusted code execution hoặc task cần hard filesystem isolation.

Lượt Flash revision 1 đã trả SUCCESS nhưng response gồm JSON hợp schema và prose
dư, thiếu structured_output. Host giữ nguyên envelope, tách JSON candidate bằng
review thủ công có kiểm schema; không tự coi transport SUCCESS là acceptance.
CLI ghi num_turns=4 dù bridge chỉ gửi một request; response tail cho thấy worker
từ chối finish do instruction cấm tools. Đây là bằng chứng cần sửa policy lifecycle,
không phải benchmark năng lực model. Counter reported: total_tokens=203749,
input_tokens=157056, output_tokens=46693, thinking_tokens=33093,
cache_read_tokens=105448; không cộng thêm thinking/cache vào total hoặc suy giá USD.
Chưa có bằng chứng billed cost. Revision 2 cho phép finish và sửa findings theo review.

Host không đọc auth store/key; CLI tự dùng login cache hiện có. Không có API key
UI/vault hay provider gateway đã xây trong kênh thử này.

## Cách sử dụng và kiểm tra

Prepare không gọi model:

```powershell
python scripts/research_channel.py --prepare
```

Dispatch run đã PREPARED:

```powershell
python scripts/research_channel.py --run <actual-prepared-run-path>
```

Hoặc prepare+dispatch G00: `python scripts/research_channel.py`.
Không tự replay run đã bắt đầu và không ghi đè output revision 1 tồn tại.
Correction: `python scripts/research_channel.py --revision 2` (hoặc 3), chỉ khi
review trước là REVISE cho exact result hash/revision. Previous candidate/review
được giữ trong runtime run folder. Task khác vẫn cần giao việc và bridge phù hợp;
chưa có generic auto scheduler.

Test boundary: `python -m unittest discover -s tests -v`.
Test này kiểm model data không đổi task/path scope hoặc tự ACCEPT/claim executed
commands/validation. Không gọi Gemini và không chứng minh sandbox.

Đọc state/events lúc đang chạy; source of truth của phiên bridge là status run.
Không báo completion chỉ vì CLI exit0: result/schema/evidence review là các lớp khác.
