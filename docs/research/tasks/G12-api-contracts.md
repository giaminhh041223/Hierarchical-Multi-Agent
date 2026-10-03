# G12 — Bóc tách contract API model độc lập

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G01, G08**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ04, RQ10**.
Nguồn chính: [S41](https://developers.openai.com/api/reference/overview), [S42](https://developers.openai.com/api/reference/resources/responses/methods/create), [S43](https://platform.claude.com/docs/en/api/messages/create), [S44](https://ai.google.dev/api), [S45](https://docs.z.ai/guides/overview/quick-start), [S46](https://docs.z.ai/devpack/tool/opencode), [S48](https://ai.google.dev/api/generate-content), [S49](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Chỉ đọc docs OpenAI, Anthropic, Google, Z.AI; không gọi inference/auth/key endpoint. Không cần API key để làm task.

2. Lập table mỗi API family: auth header, base URL, request primitive, model ID source, streaming/result/usage/error schema, cancel support, retry guidance, context tooling và evidence locator.

3. OpenAI Responses và Chat-compatible là contract khác; S49 CLI wrapper không phải REST JSON body. Fetch lỗi S42 phải fallback official bounded schema hoặc UNKNOWN.

4. Gemini primitive hiện tại recheck từ index S44; nếu recommend Interactions hoặc primitive khác thì ghi phạm vi. Không coi generateContent là primitive duy nhất hay tự suy endpoint mới.

5. Z.AI thường API-compatible không chứng minh every OpenAI feature hoặc CLI quota entitlement; ghi fields support có nguồn và unknown.

6. Output provider-api-contracts.json với supported/unknown fields, pricing=null nếu chưa có sources; synthetic samples không chứa key và gắn PROPOSED ở wrapper tự thiết kế.

7. Thiết kế error classification TEST_PLAN: 401/403/429/timeouts/stream cut/invalid response/unknown billing. Timeout có thể đã tính phí, không tự retry mọi request.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G12.md`
- `docs/research/results/G12.json`
- `docs/research/results/G12-provider-api-contracts.json`


Report dùng template; mỗi kết luận material có G12-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G12-A1:** 4 provider families có evidence/unknown từng trường.
- **G12-A2:** Không API call, key, fake giá/quota hoặc fabricated errors log.
- **G12-A3:** Fetch failures không bị lấp bằng CLI wrapper.
- **G12-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G12-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

