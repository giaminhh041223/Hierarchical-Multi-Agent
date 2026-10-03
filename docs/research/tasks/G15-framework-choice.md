# G15 — Đánh giá hẹp LangGraph và CrewAI

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ05, RQ08, RQ09**.
Nguồn chính: [S12](https://docs.langchain.com/oss/python/langgraph/overview), [S13](https://docs.langchain.com/oss/python/langgraph/persistence), [S14](https://docs.langchain.com/oss/python/langgraph/interrupts), [S15](https://docs.crewai.com/en/concepts/processes).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. So sánh primitives cần thật: durable task state, interrupt/resume, manager-worker handoff, retry/event integration. Không benchmark framework tổng quát.

2. LangGraph: documented checkpointer, thread identity, node replay khi resume, side effects/idempotency. RAM saver không restart durable.

3. CrewAI: hierarchical process, manager model/agent và delegation; persistence/HITL capabilities chỉ claim nếu actual sources.

4. Lập gap matrix với deterministic scheduler source-of-truth, external CLI adapter, workspace permissions và pending siblings.

5. Chọn reuse framework/stdlib engine/undecided dưới nhãn PROPOSED; AGENTS.md stdlib baseline vẫn áp dụng cho tương lai cho đến khi lead ghi quyết định có measured need.

6. Lập small future experiment so framework path với stdlib path cùng semantics, chưa chạy; không thêm dependency.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G15.md`
- `docs/research/results/G15.json`


Report dùng template; mỗi kết luận material có G15-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G15-A1:** Framework feature chỉ scope docs/version.
- **G15-A2:** Interrupt resume replay và persistent saver được nêu.
- **G15-A3:** Không chọn library vì trend hoặc thay dependency rules.
- **G15-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G15-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

