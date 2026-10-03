# G23 — Lập quyết định dùng lại, fork hoặc tự xây có bằng chứng

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G08, G13, G14, G15, G16, G17, G18, G19, G20, G21, G22**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ01, RQ04, RQ09, RQ10, RQ13, RQ17**.
Nguồn chính: claims đã review của dependencies; không tự mở rộng search.
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đánh giá ít nhất ba alternatives: configure existing product, fork/extend reference, own coordinator with bounded reusable components. Không chấm điểm cảm tính kiểu 9/10.

2. Fit matrix RQ01–RQ18: evidence claim IDs, actual gap, extension point traced, license/dependency obligations from observed text, Windows proof level và owned maintenance.

3. Dự kiến effort theo count modules/interfaces/unknowns thay số ngày bịa; không biến rank nguồn thành runtime readiness.

4. Critical gates: scoped autonomy, human pending independent tasks, provider contract compatibility, secret boundary, durability; thiếu proof=>NOT_EVALUATED_FOR_DEPLOYMENT.

5. Decision record có status PROPOSED/DEFERRED, rationale, rejected-for-scope alternatives, uncertainty, reversible experiment để resolve và who decides.

6. Map framework/gateway/workflow boundaries để tránh hai scheduler/state/retry owners. Respect AGENTS stdlib baseline hoặc trình lead justification chưa apply.

7. Không fork/clone để execute, launch product hoặc chọn final model thay user.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G23.md`
- `docs/research/results/G23.json`


Report dùng template; mỗi kết luận material có G23-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G23-A1:** Quyết định là đề xuất và có blockers cụ thể.
- **G23-A2:** License/Windows evidence scope không bị overclaim.
- **G23-A3:** Một scheduler/task-state owner và retry ownership map.
- **G23-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G23-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

