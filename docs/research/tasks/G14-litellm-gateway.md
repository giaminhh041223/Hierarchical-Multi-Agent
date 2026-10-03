# G14 — Phân tích gateway, routing và budgets LiteLLM

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ07, RQ10**.
Nguồn chính: [S16](https://docs.litellm.ai/docs/proxy/virtual_keys), [S17](https://docs.litellm.ai/docs/routing), [S18](https://docs.litellm.ai/docs/proxy/users).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc official keys/routing/users. Lập deployment/edition prerequisites cho virtual keys, model ACL, budgets/rate limits và DB.

2. Phân biệt enforced cap, estimated spend, delayed usage update và concurrency overshoot. Không khẳng định hard spend ceiling chỉ từ max_budget config.

3. Map routing algorithms/fallback/retry tới behavior documented; chỉ chọn thuật toán dưới nhãn PROPOSED.

4. Xác định retry ownership gateway vs scheduler; duplicate billable calls khi layers retry đồng thời, timeout uncertain completion.

5. Lập key ownership architecture: provider key upstream, virtual key app, project/workflow credential binding; no secrets in DB task prompts/logs.

6. Thiết kế future tests budget exhaustion/concurrent reserve/unknown usage/model ACL/fallback authfail; không run gateway.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G14.md`
- `docs/research/results/G14.json`


Report dùng template; mỗi kết luận material có G14-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G14-A1:** DB/edition assumptions hiện rõ.
- **G14-A2:** Budget config không tự thành guaranteed cap.
- **G14-A3:** Có một owner cho retry đề xuất và unknown billing handling.
- **G14-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G14-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

