# G24 — Bản thiết kế kỹ thuật và backlog triển khai sau nghiên cứu

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G23, G16, G17, G18, G19, G20, G21, G22**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ01, RQ02, RQ03, RQ04, RQ05, RQ06, RQ07, RQ08, RQ09, RQ10, RQ11, RQ12, RQ13**.
Nguồn chính: claims đã review của dependencies; không tự mở rộng search.
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Dựa decision PROPOSED hoặc DEFERRED, tạo blueprint option chosen-by-lead chưa approved; nếu critical unknown giữ conditional branches, không chốt architecture vô điều kiện.

2. Module map UI/control API/scheduler/state/events/adapters/workspace/vault/context/Skill Architect/budget/reviewer, I/O/owner/enforcement. Mọi field/module mới PROPOSED.

3. Sequence diagrams: submit→plan review→two workers→one pending→other continue→answer→resume→review→artifact; API profile/key references và official account login riêng.

4. Proposed control API hợp single-user local trust boundary: validation/auth/origin/CSRF where relevant/secret redaction/idempotency/events; không publish endpoint hoặc dùng unauthenticated localhost làm mặc định tin cậy.

5. Lập data model và migrations cần thiết, not implementation; link G17/G18 contracts thay repeat large JSON.

6. Backlog mỗi item Ixx: goal/RQs/dependencies/allowed files(proposed paths)/forbidden changes/input snapshot/steps/output/acceptance test/failure stop/rollback/unknown prerequisite. Chia nhỏ một behavior/task, không 'build whole backend'.

7. Thứ tự future work: fake deterministic scheduler→human/recovery→one documented adapter→review/workspaces→API profiles→more adapters→Skill Architect→optional benchmark/graph. Smoke inference là gate cần authorization sau, không task auto-run hiện tại.

8. Phân biệt required semantic tests với reversible docs/UI thay đổi; scenario suite phải bao pending/crash/duplicate/tool denial/key redaction/path scope. Không viết code hay run tests.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G24.md`
- `docs/research/results/G24.json`
- `docs/research/results/G24-implementation-backlog.json`


Report dùng template; mỗi kết luận material có G24-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G24-A1:** Backlog task-specific allowed paths/acceptance/stop và deps không cycle.
- **G24-A2:** Planning-only, CLI/API contracts referenced versioned.
- **G24-A3:** Conditional unknown gates và no-code/no-paid-inference được giữ.
- **G24-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G24-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

