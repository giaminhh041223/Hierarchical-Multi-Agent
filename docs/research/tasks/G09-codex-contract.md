# G09 — Contract tích hợp Codex local

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ03, RQ04, RQ11**.
Nguồn chính: [S19](https://learn.chatgpt.com/docs/non-interactive-mode), [S20](https://learn.chatgpt.com/docs/app-server), [S21](https://learn.chatgpt.com/docs/auth).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc docs official ở source lock: non-interactive exec vs app-server. Chọn đường chính dưới nhãn PROPOSED sau khi so sánh events, sessions, approvals và control.

2. Metadata allowlist duy nhất: Get-Command codex -ErrorAction SilentlyContinue; codex --version; codex --help; codex exec --help; codex app-server --help. Không exec prompt/start app-server hoặc login/status đọc credentials.

3. Lập capability contract: executable/version, documented modes, model discovery source, auth signal type, cwd, policy, streaming schema, resume/cancel, usage fields. Mỗi field ghi version/claim hoặc UNKNOWN.

4. Trace đúng official schema/example nếu đọc được; không invent app-server method/event names. Tách client auth/subscription khỏi API entitlement.

5. Ghi session isolation và version negotiation; CLI exit code, result content và acceptance là ba lớp.

6. Thiết kế sample SYNTHETIC cho success/auth-required/cancel/incompatible-version; mẫu field mới là PROPOSED, không vendor transcript.

7. Liệt kê future inference smoke test cần user authorization; không thực thi.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G09.md`
- `docs/research/results/G09.json`
- `docs/research/results/G09-codex-contract.json`


Report dùng template; mỗi kết luận material có G09-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G09-A1:** Mọi flag/method có actual official locator.
- **G09-A2:** Không đọc key hoặc chứng minh auth bằng help.
- **G09-A3:** Contract UNKNOWN cho capability không có nguồn.
- **G09-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G09-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

