# G17 — Thiết kế state machine, DAG và recovery

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G02, G04, G06, G08, G15, G16**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ05, RQ08, RQ09**.
Nguồn chính: [S33](https://www.sqlite.org/wal.html), [S47](https://www.sqlite.org/lang_transaction.html).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đề xuất exact state names/transitions; mỗi transition gồm actor/guard/atomic write/event/next eligible branches. Scheduler owns state, lead chỉ submit proposals.

2. Thiết kế task dependency readiness, failed/blocked/canceled prerequisites, pending approval/input và independent runnable siblings.

3. Thiết kế attempts/leases/retry classes/max attempts/budget reservation và completion_unknown quarantine. Numeric defaults là PROPOSED cần rationale.

4. Thiết kế human request với request_id/version/requested_scope/deadline/answer authority; không xem elapsed timeout là approval. Reject/expire không block unrelated tasks.

5. Thiết kế persistence table/index/transaction outline dưới nhãn PROPOSED; WAL và transaction docs chỉ chứng minh DB behavior trong scope documented.

6. Crash matrix: before durable dispatch, after process launch before recording PID/session, midstream, after external effect before DB result, after user answer. Mỗi row có recovery strategy và unresolved risk.

7. Viết pseudocode tối đa 60 dòng cho tick/reconcile; không Python implementation. Test plans: diamond DAG, independent pending, duplicate/late results, two schedulers competing, restart.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G17.md`
- `docs/research/results/G17.json`
- `docs/research/results/G17-scheduler-design.json`


Report dùng template; mỗi kết luận material có G17-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G17-A1:** Transitions đầy đủ terminal/pending/cancel và actor/guard.
- **G17-A2:** Crash matrix không hứa exactly-once ngoài DB.
- **G17-A3:** Concurrency/idempotency/retry ownership và acceptance boundary rõ.
- **G17-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G17-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

