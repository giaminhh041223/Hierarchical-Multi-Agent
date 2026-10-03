# G04 — Truy vết điều phối và sessions của Agent Orchestrator

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ01, RQ02, RQ05, RQ09**.
Nguồn chính: [S04](https://github.com/Untrivial-ai/agent-orchestrator).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Xác nhận repo canonical từ G01; không dùng metadata ComposioHQ cũ làm revision hiện tại.

2. Tìm entrypoint local app/orchestrator/worker session. Trace user request→orchestrator decision→worker launch→event/session persistence→UI.

3. Phân biệt model manager đề xuất hành động và deterministic service chấp nhận; ai owns task/session status, dependency và retry?

4. Lập persistence/event inventory: DB/files/bus thực có trong source, producer/consumer, sequence ordering, restart behavior.

5. Trace pending user input và independent work; nếu chỉ có session UI mà không DAG, ghi inspected scope và UNKNOWN, không suy thiếu toàn repo.

6. Trace một PR/CI/review reaction đường đi nếu trong 15-file budget; không gọi remote GitHub. Các flow không đủ budget là followup đề xuất.

7. Đọc tests liên quan; báo TEST_DEFINED và ba future scenarios: crash session, out-of-order event, pending sibling.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G04.md`
- `docs/research/results/G04.json`


Report dùng template; mỗi kết luận material có G04-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G04-A1:** Có call chain pinned và evidence cho state owner.
- **G04-A2:** Session != task DAG được phân biệt.
- **G04-A3:** Không khẳng định CI/PR hoạt động trên máy từ code/doc.
- **G04-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G04-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

