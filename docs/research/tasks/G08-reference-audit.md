# G08 — Audit chéo bằng chứng và khoảng trống các sản phẩm

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G02, G03, G04, G05, G06, G07**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ01, RQ03, RQ09, RQ10, RQ13, RQ17**.
Nguồn chính: [S01](https://github.com/andyyaro/orkestra), [S04](https://github.com/Untrivial-ai/agent-orchestrator), [S05](https://github.com/stoneforge-ai/stoneforge), [S07](https://github.com/BloopAI/vibe-kanban), [S08](https://www.vibekanban.com/blog/shutdown).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Tổng hợp requirement fit theo từng repo bằng claim IDs từ reports được review; không copy unsupported assertion.

2. Dùng Vibe Kanban như UI/workspace reference phụ. Ghi tình trạng community/local theo official shutdown notice, không kết luận project biến mất.

3. Lập conflict ledger: version/doc/code/runtime, Orkestra Antigravity JSON, Windows distribution vs execution, knowledge vs graph, permission bypass vs scoped autonomy.

4. Với mỗi requirement ghi SATISFIED_IN_DOCS, IMPLEMENTATION_TRACED, NOT_FOUND_IN_INSPECTED_SCOPE, UNKNOWN; không dùng boolean support chung.

5. Liệt kê critical unknowns chặn quyết định reuse/fork/build, kèm experiment cần quyền ở giai đoạn sau.

6. Đưa recommendation phạm vi nghiên cứu tiếp theo, không quyết định nền. Giới hạn đọc chéo claim extracts cần thiết thay toàn bộ repo.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G08.md`
- `docs/research/results/G08.json`


Report dùng template; mỗi kết luận material có G08-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G08-A1:** Tất cả cell material map claim IDs có evidence level.
- **G08-A2:** Unknown quan trọng không bị loại khỏi summary.
- **G08-A3:** G08 chỉ gate nghiên cứu reference; không tuyên bố production fit.
- **G08-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G08-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

