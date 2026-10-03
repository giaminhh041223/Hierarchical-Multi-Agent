# G13 — Phân tích Dify cho API credentials và human workflow

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ09, RQ10, RQ16**.
Nguồn chính: [S09](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose), [S10](https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers), [S11](https://docs.dify.ai/en/cloud/use-dify/nodes/human-input).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Lập version/edition inventory theo sources: Cloud vs self-host/Community/Enterprise. Không dùng Cloud docs làm evidence feature self-host hiện tại.

2. Trace documented provider credential management và workflow environment variables: secret owner, storage/encryption claim, exposure to node/plugin và lifecycle. Không tải config/env thật.

3. Phân tích Human Input pause/resume: identity, expiration, repeated submission, persisted waiting state, independent branch semantics; thiếu doc chuyển UNKNOWN.

4. Lập fit/gap so với local CLI orchestrator: Dify engine/task state vs lead engine, plugin execution vs agent CLI, ingress n8n inspiration.

5. Đề xuất architecture boundary và một sequence PROPOSED API-only workflow không side effect, credential references thay actual key.

6. Không self-host/install/start Dify. Liệt kê validation tương lai theo edition/license/version.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G13.md`
- `docs/research/results/G13.json`


Report dùng template; mỗi kết luận material có G13-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G13-A1:** Cloud/selfhost evidence có cột edition.
- **G13-A2:** Key/environment/workflow permissions không bị gộp.
- **G13-A3:** Không kết luận Dify điều phối mọi coding CLI.
- **G13-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G13-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

