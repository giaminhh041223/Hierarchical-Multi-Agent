# G25 — Audit bàn giao và ma trận truy xuất bằng chứng

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G24, G00, G01, G08, G09, G10, G11, G12, G13, G14, G15, G16, G17, G18, G19, G20, G21, G22, G23**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ17, RQ18**.
Nguồn chính: claims đã review của dependencies; không tự mở rộng search.
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Tạo traceability RQ→design section→claim IDs→source locators→Ixx acceptance scenario. Không yêu cầu optional graph/benchmark như user mandatory.

2. Kiểm tra mọi quote/flag/route/path/version/score/hash/price trong bản bàn giao so actual evidence; ghi missing link, không tự điền.

3. Audit claims DOC vs CODE vs OBSERVED; code đọc không runtime proof, synthetic fixture không actual transcript; fetch failure ở manifest còn hiện rõ.

4. Audit state/pending/retry/human authority/permission/vault/context/resource ownership và contradictions giữa modules. Đề nghị correction đúng Gxx, không sửa reports dependencies.

5. Lập unresolved ledger: impact/blocking/runtime permission needed/owner/next bounded experiment; quyết định readiness chỉ proposal, không tự ACCEPT.

6. Tổng hợp handoff summary cho user/lead, task list và đầu việc đầu tiên khi future implementation được authorize. G25 là self-audit, reviewer independent sẽ kiểm tra lại.

7. Stop sau reports/G25.md/results/G25.json và sidecar traceability.json; không triển khai hoặc tự giao implementation task.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G25.md`
- `docs/research/results/G25.json`
- `docs/research/results/G25-traceability.json`


Report dùng template; mỗi kết luận material có G25-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G25-A1:** Có traceability đủ 18 RQs, optional requirements đúng loại.
- **G25-A2:** Không tự tạo independent acceptance.
- **G25-A3:** Unknowns và prerequisite runtime chưa verified không mất khỏi summary.
- **G25-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G25-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

