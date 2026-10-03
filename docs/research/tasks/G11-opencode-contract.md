# G11 — Contract OpenCode CLI và server

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ03, RQ04, RQ10, RQ11**.
Nguồn chính: [S27](https://opencode.ai/docs/cli/), [S28](https://opencode.ai/docs/server/), [S29](https://opencode.ai/docs/permissions/), [S46](https://docs.z.ai/devpack/tool/opencode).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc CLI/server/permissions official. So sánh one-shot CLI với long-lived server về session/events/approvals/secrets/localhost scope.

2. Metadata allowlist: Get-Command opencode -ErrorAction SilentlyContinue; opencode --version; opencode --help. Subcommand help sau khi tên được doc xác nhận. Không run prompt/serve/web hoặc đọc endpoint config/auth.

3. Lập capability/transport table: documented routes/events/options có section, model/provider catalog, session control, credentials owner, usage and errors.

4. Trace Z.AI integration theo docs S46, giữ plan/API endpoint/credential scope UNKNOWN nếu chưa đủ. Không gọi auth hoặc login.

5. Thiết kế local server ownership PROPOSED: lifecycle, port binding, process health, request identity, cancellation, tenant/project isolation và secret redaction.

6. Output synthetic contract samples; migration/version mismatch và server disconnect scenarios; không start server để lấy evidence.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G11.md`
- `docs/research/results/G11.json`
- `docs/research/results/G11-opencode-contract.json`


Report dùng template; mỗi kết luận material có G11-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G11-A1:** CLI/server contracts được phân biệt.
- **G11-A2:** Không invented routes hoặc endpoint credentials.
- **G11-A3:** Usage/session/cancel có verified sources hoặc UNKNOWN.
- **G11-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G11-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

