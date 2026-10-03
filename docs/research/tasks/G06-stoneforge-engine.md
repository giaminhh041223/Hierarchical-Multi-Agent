# G06 — Bóc tách roles, dispatch và persistent knowledge Stoneforge

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ02, RQ05, RQ06, RQ09, RQ15**.
Nguồn chính: [S05](https://github.com/stoneforge-ai/stoneforge).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Trace Director→task creation/pool→worker assignment→steward/reviewer nếu có. Không map role từ tên sang chức năng chưa đọc.

2. Lập state/dependency/priority/lease ownership, SQLite/JSONL hoặc storage thực và transaction boundaries.

3. Trace channels: task message, broadcast, result, interruption. Đánh giá delivery ordering, duplicate events và quyền sửa shared knowledge.

4. Trace knowledge write/read/search: identity, provenance, typed relations, invalidation, project scope. Không gọi nó knowledge graph nếu source chỉ có notes.

5. Trace one restart/pending path và tests định nghĩa tương ứng; không chạy source.

6. Map reuse questions tới RQ06/RQ09/RQ15; liệt kê tối đa ba gaps có inspected scope.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G06.md`
- `docs/research/results/G06.json`


Report dùng template; mỗi kết luận material có G06-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G06-A1:** Mỗi role/state/storage claim có locator pinned.
- **G06-A2:** Memory/messages/graph được phân biệt.
- **G06-A3:** Recovery không nâng thành exactly-once.
- **G06-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G06-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

