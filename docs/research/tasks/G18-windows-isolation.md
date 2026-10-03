# G18 — Thiết kế workspace, process policy và credential vault Windows

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G03, G05, G07, G09, G10, G11, G16**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ01, RQ08, RQ10, RQ11, RQ12**.
Nguồn chính: [S32](https://git-scm.com/docs/git-worktree), [S35](https://learn.microsoft.com/en-us/windows/win32/secauthn/credentials-management), [S36](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata), [S37](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đề xuất workspace policy: base ref/worktree/task branch/change review/conflict/cleanup; dirty shared checkout được giữ nguyên. Git không phải requirement mọi project và không phải sandbox.

2. Threat-boundary table cho prompts/files/network/process/secrets: enforcement layer, allowed scope, denied behavior, tests. Nếu CLI không enforce filesystem scope, fail-closed hoặc explicit weaker mode; không hứa OS isolation.

3. Windows path cases: absolute resolution, drive boundary, case, Unicode/spaces, symlink/junction traversal; allowlist path check phải dựa resolved target và quyền thật.

4. Process lifecycle proposal dùng platform capabilities có nguồn: tree ownership, cancellation, timeout, crash, descendant termination; Job Objects là candidate cần runtime tests, không guarantee mọi process.

5. API key UI→host-only vault/reference→per-run env injection→redacted event→rotation; đánh giá Credential Manager/DPAPI/RAM-only và user/machine/decryption scope. Không plaintext persisted key, không blanket env copy.

6. Client account login do official client quản lý; app chỉ trigger future documented login flow khi user yêu cầu và nhận safe status. Không centralize passwords/session token scraping.

7. Lập scenarios junction escape, secret in stderr, child orphan, canceled task writes, worktree conflict và restart with vault unavailable. Chưa chạy hoặc sửa settings.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G18.md`
- `docs/research/results/G18.json`
- `docs/research/results/G18-windows-boundaries.json`


Report dùng template; mỗi kết luận material có G18-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G18-A1:** Worktree/prompt/CWD không bị gọi sandbox.
- **G18-A2:** Secret lifecycle và path/process tests cụ thể.
- **G18-A3:** Mode không đủ enforce phải ghi limitation chặn capability claim.
- **G18-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G18-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

