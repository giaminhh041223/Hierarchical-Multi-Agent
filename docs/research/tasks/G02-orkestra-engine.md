# G02 — Truy vết engine và recovery của Orkestra

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ05, RQ08, RQ09**.
Nguồn chính: [S01](https://github.com/andyyaro/orkestra), [S02](https://github.com/andyyaro/orkestra/blob/main/docs/architecture/ARCHITECTURE.md).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Chỉ dùng source revision G01 đã pin. Tìm entrypoint và scheduler bằng tree/rg, không đoán tên file. Ghi inventory tối đa 15 code files đã mở.

2. Trace đường đi submit→plan→dependency eligibility→dispatch→result→terminal state. Mỗi cạnh có caller/callee và claim CODE_TRACED hoặc UNKNOWN.

3. Lập bảng task states và transitions: actor ghi state, validation, transaction boundary, persisted fields, event side effects.

4. Trace dependency failure và human pending; chứng minh bằng code liệu task độc lập còn dispatch được. Nếu chỉ có README, ghi DOCUMENTED.

5. Trace retry attempt identity, lease/timeout, process crash và restart reconciliation. Phân biệt checkpoint với exactly-once effect ngoài DB.

6. Đọc tests liên quan nếu có; record TEST_DEFINED, không chạy. Lập ba scenario future test: sibling pending, restart mid-dispatch, duplicate result.

7. Kết luận phần reuse được và phần còn thiếu, tham chiếu claims; không fork hoặc implement.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G02.md`
- `docs/research/results/G02.json`


Report dùng template; mỗi kết luận material có G02-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G02-A1:** Flow có source locators ở caller/callee, không chỉ diagram từ README.
- **G02-A2:** State persistence/recovery có transaction hoặc UNKNOWN.
- **G02-A3:** Ba test plans có setup, trigger và observable expectation.
- **G02-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G02-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

