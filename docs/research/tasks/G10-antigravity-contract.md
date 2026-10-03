# G10 — Contract Antigravity cho Claude và Gemini

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ03, RQ04, RQ08, RQ11**.
Nguồn chính: [S22](https://antigravity.google/docs/cli/headless/), [S23](https://antigravity.google/docs/permissions/), [S24](https://antigravity.google/docs/cli/install/), [S25](https://antigravity.google/docs/models/), [S26](https://antigravity.google/docs/cli/reference/).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc official headless/permissions/install/models/reference theo cùng version khi có. Phân biệt provider model catalog và account entitlement.

2. Metadata allowlist: Get-Command agy -ErrorAction SilentlyContinue; agy --version; agy --help. Subcommand --help chỉ sau khi tên xuất hiện trong help/docs đã đọc. Không chạy prompt/model listing có khả năng inference, login hoặc sửa settings.

3. Lập launch/events/result contract chỉ từ verified docs/help. Nếu docs có JSON output hoặc usage cumulative, ghi đúng scope và sample source; không dựa README third-party.

4. Xác định permission scope: per-request/project/global; nếu không thể enforce per-task bằng interface documented, đánh dấu unsupported/UNKNOWN theo evidence và đề xuất fallback fail-closed.

5. Phân tích soft denial: tool denied trong message nhưng exit0 là hypothesis TEST_PLAN trừ khi có official code/doc/log. Đề xuất result normalizer để không tự nghiệm thu exit0.

6. Phân tích model choice Claude/Gemini, active session reuse, cancel và auth lifecycle. Auth/catalog không xác nhận có quota.

7. Output synthetic failure fixtures và future experiments: invalid model, auth absent, tool denied, cancel, resumed usage. Không thay global config.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G10.md`
- `docs/research/results/G10.json`
- `docs/research/results/G10-antigravity-contract.json`


Report dùng template; mỗi kết luận material có G10-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G10-A1:** Contract không dùng flag bịa; các tên help-only không chạy.
- **G10-A2:** Permission boundary và cumulative counters được nêu hoặc UNKNOWN.
- **G10-A3:** Claude/Gemini entitlement giữ chưa xác minh.
- **G10-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G10-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

