# G22 — Thiết kế budgets, resource pools và telemetry

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G14, G16, G17, G19, G21**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ07, RQ08, RQ09, RQ10**.
Nguồn chính: claims đã review của dependencies; không tự mở rộng search.
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đề xuất resource profile: client/API/account alias/model/quota group/concurrency/env profile/credential_ref; alias không chứa personal secret.

2. Accounting schema: reserved/estimated/observed/reconciled/unknown costs/tokens; per task/attempt/project/window, model price source+date. Unknown price không cost0.

3. Concurrency cap và reservation transaction trước dispatch; distinguish app stop policy vs provider billed ceiling và overshoot stream/unknown completion.

4. Retry/refund/resume rules: cancel không chắc refund, subscription usage không USD price, double counting cumulative counters và gateway retries.

5. Trace schema task→attempt→adapter→session→artifact→review/human request; event redaction before persistence, retention và project access.

6. Failure policy table cho rate-limit/auth/key rotation/budget stop/no telemetry; pending branch và remaining capacity remain deterministic.

7. Future tests two dispatch reservations, stream late usage, lost terminal event, quota group shared clients, redact secret; chưa đo tiết kiệm.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G22.md`
- `docs/research/results/G22.json`
- `docs/research/results/G22-budget-observability-design.json`


Report dùng template; mỗi kết luận material có G22-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G22-A1:** Unknown usage/cost không bằng zero.
- **G22-A2:** Reservation/reconcile/retry ownership rõ.
- **G22-A3:** Không hứa hard billed cap từ accounting cục bộ.
- **G22-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G22-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

