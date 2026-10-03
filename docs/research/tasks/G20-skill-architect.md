# G20 — Thiết kế Skill Architect và phân phối skills/plugins

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G00, G01, G16, G18**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ06, RQ13**.
Nguồn chính: [S30](https://agentskills.io/specification), [S31](https://modelcontextprotocol.io/specification/2026-07-28).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc Agent Skills/MCP version pinned; phân biệt skill instructions, executable scripts, MCP tools, plugin bundles và auth connections.

2. Thiết kế Skill Architect lifecycle: task needs→candidate search→source/license/pinned revision→compatibility/permission review→lead approval policy→scoped distribution→revoke/update.

3. Không cài skill/plugin. Chỉ search tối đa hai official primary GitHub candidates nếu cần minh họa; stars là discovery metadata, không quality proof.

4. Manifest PROPOSED: package/source/revision/hash/license/requires/tools/permissions/compatible client/task scope/reviewer/version/expiry. Hash UNKNOWN nếu không thực fetch.

5. Supply-chain and prompt boundary: untrusted instructions không nâng quyền, remote executable không auto run, changing branch không immutable, dependency/license unknown blocks installation readiness.

6. Design selection evidence: relevance to repo/language/task, measurable skill usefulness test, conflict with worker rules, instruction precedence, context size cost.

7. Tạo proposal một distribution plan SYNTHETIC cho lead/reviewer/code worker/research worker; không cần giả vờ tìm được skill mạnh nhất.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G20.md`
- `docs/research/results/G20.json`
- `docs/research/results/G20-skill-manifest-proposal.json`


Report dùng template; mỗi kết luận material có G20-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G20-A1:** Search/ranking/install là các state riêng.
- **G20-A2:** Có version/license/permissions/rollback và missing-proof behavior.
- **G20-A3:** Không install hoặc bảo đảm an toàn chỉ vì Github/star count.
- **G20-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G20-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

