# G16 — Thiết kế contract adapter chung và capability registry

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G09, G10, G11, G12**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ03, RQ04, RQ06, RQ10, RQ11**.
Nguồn chính: claims đã review của dependencies; không tự mở rộng search.
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Tổng hợp verified fields từ bốn contract; adapter không được khai capability true chỉ vì chung interface.

2. Đề xuất adapter protocol PROPOSED với discover/prepare/start/observe/cancel/reconcile; transport CLI/server/native API giữ khác biệt. Unsupported method explicit.

3. Lập capability states: installed, catalogued, authenticated, inference_verified, quota_known; timestamp/version/account profile ref và invalidation rules.

4. Đề xuất event envelope: event_id/task_id/attempt_id/session_id/sequence/type/time/provenance/payload, usage delta vs cumulative, terminal outcome. Đây là tên field app đề xuất, không vendor schema.

5. Đề xuất outcome classifier: success candidate, auth_required, rate_limited, tool_denied, retryable_failure, completion_unknown, canceled. Task acceptance thuộc reviewer/scheduler.

6. Lập mapping table vendor field→normalized field→evidence claim→unsupported handling; giữ UNKNOWN khi chưa biết.

7. Output adapter-contract.json và synthetic fixtures cho success, malformed stream, duplicate terminal event, cancel race. Không tạo adapter implementation.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G16.md`
- `docs/research/results/G16.json`
- `docs/research/results/G16-adapter-contract.json`


Report dùng template; mỗi kết luận material có G16-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G16-A1:** Field normalized có PROPOSED label và mapping evidence.
- **G16-A2:** Registry không phát sinh auth/quota fact từ discovery.
- **G16-A3:** Completion_unknown không tự biến failure hoặc success.
- **G16-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G16-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

