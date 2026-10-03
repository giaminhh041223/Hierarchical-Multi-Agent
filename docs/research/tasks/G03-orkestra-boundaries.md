# G03 — Bóc tách adapter, workspace và review gates Orkestra

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G02**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ04, RQ06, RQ08, RQ12**.
Nguồn chính: [S01](https://github.com/andyyaro/orkestra), [S03](https://github.com/andyyaro/orkestra/blob/main/docs/SECURITY_MODEL.md).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Discover adapter registry và các provider thực trong pinned source; phân biệt listed/implemented/test-defined. OpenCode không được tự thêm vào danh sách.

2. Trace một worker launch→event parsing→completion→review/test gate. Ghi CLI argv/env contract đúng source; không chạy argv.

3. Trace worktree create/base branch/task path, merge conflict, cleanup và retention. CWD/worktree không chứng minh sandbox.

4. Trace tool policy, permission escalation và human decision ownership. So sánh claim security doc với code; ghi vùng không kiểm tra.

5. Đối chiếu tài liệu Orkestra về Antigravity JSON với S22/S26 ở đúng ngày/version; ghi conflict, không chọn bên theo độ mới nếu thiếu revision match.

6. Chọn ba failure scenarios: tool denied nhưng process success, reviewer reject, worktree merge conflict. Thiết kế acceptance observations và người có quyền quyết định.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G03.md`
- `docs/research/results/G03.json`


Report dùng template; mỗi kết luận material có G03-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G03-A1:** Adapter inventory có evidence level và Windows UNKNOWN khi chưa chạy.
- **G03-A2:** Ranh giới permission và sandbox được nêu đúng.
- **G03-A3:** Conflict Antigravity doc/code được ghi rõ scope.
- **G03-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G03-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

