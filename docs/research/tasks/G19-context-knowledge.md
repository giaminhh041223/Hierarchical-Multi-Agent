# G19 — Thiết kế context, kênh trao đổi và knowledge tối thiểu

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G06, G16, G17**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ06, RQ07, RQ15**.
Nguồn chính: [S34](https://www.sqlite.org/fts5.html).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Phân loại durable facts/artifacts/decisions vs temporary scratch/model reasoning. Không thu thập chain-of-thought; dùng concise rationale/evidence.

2. Đề xuất task brief envelope: objective/scope/inputs/version refs/expected output/acceptance/budget/stop, scoped worker inbox và lead summary.

3. Thiết kế retrieval trước toàn graph: SQLite metadata+FTS candidate, project/access scope, retrieval budget, dedupe, stale facts, conflicting claims.

4. Graph extension PROPOSED chỉ nếu measurable need: typed edges DERIVED_FROM/DEPENDS_ON/VERIFIED_BY/CONFLICTS_WITH, version/time/provenance, no inferred edge presented as truth.

5. Compaction policy: preserve decisions/unknowns/source refs/request authority; summaries không replace original artifacts. Giới hạn context theo provider known/unknown.

6. Token accounting cho retrieved context, prompts, output, caching/reasoning nếu vendor report; counters cumulative vs delta, reset/resume. Estimate != billed.

7. Lập evaluation plan cùng corpus/task: naive full context vs scoped retrieval, success evidence coverage/stale retrieval/tokens/time; chưa có kết quả tốc độ.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G19.md`
- `docs/research/results/G19.json`
- `docs/research/results/G19-context-knowledge-design.json`


Report dùng template; mỗi kết luận material có G19-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G19-A1:** Knowledge design không ép Neo4j/vector stack chưa cần.
- **G19-A2:** Scope/provenance/conflict/invalidation hiện rõ.
- **G19-A3:** Không khẳng định tiết kiệm token/tăng tốc khi chưa đo.
- **G19-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G19-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

