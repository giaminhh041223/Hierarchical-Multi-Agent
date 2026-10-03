# G07 — Bóc tách provider, review và permissions Stoneforge

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G06**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ04, RQ08, RQ11, RQ12**.
Nguồn chính: [S05](https://github.com/stoneforge-ai/stoneforge), [S06](https://docs.stoneforge.ai/guides/multi-provider/).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Trace multi-provider registry và launch flow Claude Code/OpenCode/Codex nếu thực có. So sánh docs với source; không dùng model name làm provider capability.

2. Trace credential ownership: underlying client auth vs central vault; chỉ đọc code/docs, không đọc local credentials.

3. Kiểm tra defaults permission bypass và override có enforcement ở launch hay chỉ instructions. Ghi flags đúng version/source.

4. Trace steward/review/merge acceptance và ownership khi worker error hoặc human pending; fail-closed và retry behavior.

5. Đề xuất boundary cho yêu cầu user: auto edit assigned folder, side effect ngoài quyền phải pending; không thay config Stoneforge.

6. Lập scenarios key missing, tool bypass configured, reviewer reject, merge conflict; output expected behavior của reference vs proposed local policy tách cột.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G07.md`
- `docs/research/results/G07.json`


Report dùng template; mỗi kết luận material có G07-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G07-A1:** Defaults và override có code evidence hoặc UNKNOWN.
- **G07-A2:** Auth owner và central-key gap không bị gộp.
- **G07-A3:** Không hứa isolation từ prompt/worktree.
- **G07-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G07-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

