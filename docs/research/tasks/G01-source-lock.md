# G01 — Xác minh và khóa nguồn tham khảo

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G00**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ17, RQ18**.
Nguồn chính: [S01](https://github.com/andyyaro/orkestra), [S02](https://github.com/andyyaro/orkestra/blob/main/docs/architecture/ARCHITECTURE.md), [S03](https://github.com/andyyaro/orkestra/blob/main/docs/SECURITY_MODEL.md), [S04](https://github.com/Untrivial-ai/agent-orchestrator), [S05](https://github.com/stoneforge-ai/stoneforge), [S06](https://docs.stoneforge.ai/guides/multi-provider/), [S07](https://github.com/BloopAI/vibe-kanban), [S08](https://www.vibekanban.com/blog/shutdown), [S09](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose), [S10](https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers), [S11](https://docs.dify.ai/en/cloud/use-dify/nodes/human-input), [S12](https://docs.langchain.com/oss/python/langgraph/overview), [S13](https://docs.langchain.com/oss/python/langgraph/persistence), [S14](https://docs.langchain.com/oss/python/langgraph/interrupts), [S15](https://docs.crewai.com/en/concepts/processes), [S16](https://docs.litellm.ai/docs/proxy/virtual_keys), [S17](https://docs.litellm.ai/docs/routing), [S18](https://docs.litellm.ai/docs/proxy/users), [S19](https://learn.chatgpt.com/docs/non-interactive-mode), [S20](https://learn.chatgpt.com/docs/app-server), [S21](https://learn.chatgpt.com/docs/auth), [S22](https://antigravity.google/docs/cli/headless/), [S23](https://antigravity.google/docs/permissions/), [S24](https://antigravity.google/docs/cli/install/), [S25](https://antigravity.google/docs/models/), [S26](https://antigravity.google/docs/cli/reference/), [S27](https://opencode.ai/docs/cli/), [S28](https://opencode.ai/docs/server/), [S29](https://opencode.ai/docs/permissions/), [S30](https://agentskills.io/specification), [S31](https://modelcontextprotocol.io/specification/2026-07-28), [S32](https://git-scm.com/docs/git-worktree), [S33](https://www.sqlite.org/wal.html), [S34](https://www.sqlite.org/fts5.html), [S35](https://learn.microsoft.com/en-us/windows/win32/secauthn/credentials-management), [S36](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata), [S37](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [S38](https://www.swebench.com/), [S39](https://www.tbench.ai/), [S40](https://artificialanalysis.ai/methodology), [S41](https://developers.openai.com/api/reference/overview), [S42](https://developers.openai.com/api/reference/resources/responses/methods/create), [S43](https://platform.claude.com/docs/en/api/messages/create), [S44](https://ai.google.dev/api), [S45](https://docs.z.ai/guides/overview/quick-start), [S46](https://docs.z.ai/devpack/tool/opencode), [S47](https://www.sqlite.org/lang_transaction.html), [S48](https://ai.google.dev/api/generate-content), [S49](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).


## 2. Công việc theo thứ tự

1. Đọc sources.json; lập manifest đúng 49 nguồn. Ghi requested URL, resolved URL, fetched_at, status, publisher, loại evidence và lý do khi không truy cập được. Không ghi fetched nếu chưa mở. Revision đầu chỉ recheck bốn repo S01/S04/S05/S07 và tối đa tám trang contract ưu tiên S19/S20/S22/S23/S26/S27/S28/S29; nguồn khác ghi NOT_RECHECKED và giữ historical status riêng. Không tải hết 49 trang vào một context. Scope G01 là baseline manifest + repo pin, không certify toàn bộ tài liệu.

2. Với Orkestra, AO, Stoneforge, Vibe Kanban: tra public metadata, license file và revision thực; pin một commit đầy đủ và ghi vì sao chọn revision. Không dùng main như immutable snapshot.

3. Nếu cần cache source, chỉ đặt dưới .research/repos/<project>/; cho phép git metadata, clone --no-checkout và git show/list source. Không checkout để chạy, không init submodule, LFS, hooks, package install hoặc scripts. Không sửa repo dự án người dùng.

4. Với web: lưu section locator và fingerprint SHA-256 của nội dung thực đã lấy khi công cụ cho phép. Nếu không lấy raw content, content_hash=null và hash_status=NOT_AVAILABLE; không hash một summary rồi gọi hash trang.

5. S42/S48 từng fetch lỗi ở khảo sát trước: ghi FAILED_HISTORICAL/NOT_RECHECKED nếu chưa lấy lại; việc recheck theo scope G12. S49 là tài liệu CLI wrapper, không thay thế REST schema S42. Version MCP/Gemini primitive chưa recheck giữ UNKNOWN; tasks G20/G12 xác minh khi dùng.

6. Tách license OBSERVED_FROM_FILE khỏi legal interpretation; sửa redirect trong sidecar, không sửa sources.json gốc. Chỉ record hai official nguồn bổ sung nếu cần.

7. Trả manifest source-lock.json với entry cho mọi nguồn, acquisition method và state thực. Nguồn chưa recheck/không fetch/pin được giữ NOT_RECHECKED/UNKNOWN/FAILED; task phụ thuộc code chưa pin phải dừng nhánh đó. Task documentation downstream được tự recheck đúng sources assigned và lưu locators trong output riêng, không sửa source-lock dependency. Nếu cần thêm source acquisition, lead giao revision G01 có phạm vi bổ sung rõ, không tự nối vòng nghiên cứu.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G01.md`
- `docs/research/results/G01.json`
- `docs/research/results/G01-source-lock.json`
- Ngoại lệ: source-only cache trong `.research/repos/` và `.research/web/`. Không execute nội dung cache.

Report dùng template; mỗi kết luận material có G01-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G01-A1:** Manifest có đủ 49 source IDs; không có revision/hash bịa.
- **G01-A2:** Bốn repo có revision hoặc blocker cụ thể; bằng chứng license có locator.
- **G01-A3:** Fetch failure và wrapper-vs-REST được giữ rõ.
- **G01-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G01-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

