# G00 — Chốt yêu cầu và ranh giới nghiên cứu

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Không có dependency. Có thể thực hiện ngay sau khi lead giao đúng task này.

Requirements: **RQ01, RQ02, RQ03, RQ04, RQ05, RQ06, RQ07, RQ08, RQ09, RQ10, RQ11, RQ12, RQ13, RQ14, RQ15, RQ16, RQ17, RQ18**.
Nguồn chính: claims đã review của dependencies; không tự mở rộng search.


## 2. Công việc theo thứ tự

1. Đọc BRIEF.md, README.md, PRODUCT_PLAN.md, INTEGRATIONS.md và index docs/research/README.md. Chỉ dùng phần liên quan scope; không audit source Python/UI nháp hoặc đọc tất cả task definitions.

2. Lập bảng RQ01–RQ18: yêu cầu nguyên văn được diễn giải, mandatory/exploratory/inspiration, tiêu chí có thể kiểm chứng, quyết định chưa được người dùng chốt. Không biến đề xuất stack hoặc model thành user requirement.

3. Tách historical local observation khỏi current verification. Liệt kê installed/catalog/auth/inference/quota là năm trường riêng; trường chưa chứng minh ghi UNKNOWN.

4. Xác định MVP boundaries để đánh giá, dưới nhãn PROPOSED: local single-user, lead/reviewer/workers/Skill Architect, pending branch, kết nối CLI và API. Benchmark/graph chỉ là candidate extension.

5. Lập danh sách câu hỏi cần nghiên cứu, map sang G01–G25; câu hỏi cần quyền/account/runtime phải chuyển future experiment, không hỏi key ngay.

6. Đánh dấu xung đột giữa tài liệu nháp và BRIEF; BRIEF về planning-only thắng. Không sửa tài liệu nguồn.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G00.md`
- `docs/research/results/G00.json`


Report dùng template; mỗi kết luận material có G00-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G00-A1:** Bảng requirements đầy đủ 18 ID và loại yêu cầu; mỗi đề xuất có nhãn.
- **G00-A2:** Historical observation không bị nâng thành auth/inference hiện tại.
- **G00-A3:** Không chốt stack, model, budget hoặc SLA thay người dùng.
- **G00-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G00-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

