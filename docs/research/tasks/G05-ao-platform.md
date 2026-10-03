# G05 — Đánh giá AO trên Windows và discovery tài nguyên

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G04**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ03, RQ04, RQ11, RQ12**.
Nguồn chính: [S04](https://github.com/Untrivial-ai/agent-orchestrator), [S32](https://git-scm.com/docs/git-worktree), [S37](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc platform build/distribution metadata và launch code. Windows download không tự chứng minh runtime của mọi client.

2. Lập matrix từng harness discovered: installed detection, version, model catalog, auth signal, inference check, session reuse/cancel. Trường không có code trace ghi UNKNOWN.

3. Trace shell/process creation, path quoting, spaces/Unicode, executable resolution và terminate descendants trên Windows. Không launch app.

4. Trace workspace implementation và assumptions Git availability/base ref/dirty checkout. Đề xuất cách tránh ghi đè worktree người dùng.

5. Xác định secret owner và metadata/UI discovery có đọc config chứa key không; không mở auth files trên máy.

6. Lập Windows experiment plan với fixture path có spaces/Unicode, kill child tree, client missing, dirty Git state; ghi là TEST_PLAN chưa chạy.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G05.md`
- `docs/research/results/G05.json`


Report dùng template; mỗi kết luận material có G05-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G05-A1:** Windows support được chia distribution/code/test/runtime.
- **G05-A2:** Discovery 5 trạng thái không gộp.
- **G05-A3:** Experiments có quyền cần thiết và observable outputs.
- **G05-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G05-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

