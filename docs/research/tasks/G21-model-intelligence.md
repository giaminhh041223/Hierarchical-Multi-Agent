# G21 — Thiết kế registry benchmark và lựa chọn model

**Mode:** RESEARCH_ONLY. **Trạng thái giao việc:** NOT_STARTED. **Revision đầu:** 1.
**Project root:** `D:\Hierarchical-Multi-Agent`.

## 1. Input và dependency gate

Đọc `AGENTS.md`, [BRIEF](../BRIEF.md), [GEMINI_RULES](../GEMINI_RULES.md), [report template](../templates/REPORT_TEMPLATE.md), [result schema](../result.schema.json).
Chỉ bắt đầu khi reviewer độc lập đã ACCEPT/ACCEPT_WITH_UNKNOWNS: **G00, G01, G16**. Đọc claim extracts và result/review của đúng dependency, không nạp toàn bộ reports. ACCEPT_WITH_UNKNOWNS không cho phép dùng unknown như capability true.

Requirements: **RQ02, RQ03, RQ07, RQ14**.
Nguồn chính: [S38](https://www.swebench.com/), [S39](https://www.tbench.ai/), [S40](https://artificialanalysis.ai/methodology).
Code tracing chỉ trên revision đã khóa trong G01-source-lock.json. Thiếu snapshot/locator thì UNKNOWN hoặc PARTIAL, không đoán.

## 2. Công việc theo thứ tự

1. Đọc benchmark methodologies thay lấy leaderboard làm recommendation chung. SWE-bench/Terminal-Bench/intelligence index đo scope khác nhau.

2. Thiết kế registry entry: provider/model/version/date/task family/harness/tools/token budget/metric/score/source/license/price snapshot/limitations. Scores chưa đọc giữ null, không tạo ví dụ số có vẻ thật.

3. Lập comparability rules: cùng dataset/version/harness/budget/model variant; khác điều kiện không xếp hạng trực tiếp.

4. Tách benchmark external từ local observed capability/account availability/latency/cost/quota. Mạnh nhất không phải tên model hoặc price cao nhất.

5. Đề xuất routing objective constrained: quality threshold/capability/tool policy/user model allowlist/budget/time. Lead/reviewer cần diversity hay model chung là design tradeoff, không guarantee.

6. Freshness/update plan: timestamp/invalidations/model aliases/retired IDs/provenance/conflicts; offline registry không phải knowledge current vĩnh viễn.

7. Lập future local evaluation plan và no-data routing fallback yêu cầu user chọn; không gọi model hoặc copy leaderboard toàn bảng.

## 3. Đầu ra và ranh giới ghi file

Chỉ tạo/sửa:
- `docs/research/reports/G21.md`
- `docs/research/results/G21.json`
- `docs/research/results/G21-model-registry-proposal.json`


Report dùng template; mỗi kết luận material có G21-Cnn và evidence level/locator. JSON dùng schema; sidecar thiết kế có `artifact_kind: PROPOSED`, sample có `SYNTHETIC`, metadata nguồn chỉ là `SOURCE_SNAPSHOT` khi đã lấy thực. Sidecar ghi task_id/revision và references; không chứa secrets.
Không sửa source ứng dụng, task/schema gốc, sources.json, output task khác, reviews hoặc trạng thái tasks.json. Report là analysis; pseudocode/schema/API proposal không phải implementation.

## 4. Tiêu chí để gửi review

- **G21-A1:** Score/giá chưa verified là null.
- **G21-A2:** Comparability/freshness/source và local entitlement tách riêng.
- **G21-A3:** Không tự chọn paid model hay claim maximum efficiency.
- **G21-A4:** Hai output bắt buộc hợp format; report/JSON claims nhất quán; unknown/conflict/không chạy test ghi rõ.
- **G21-A5:** Mỗi bước có kết quả hoặc blocker/UNKNOWN có cách xác minh; không fabricated evidence. PARTIAL hợp lệ khi thiếu input, nhưng không tính scope đó đã hoàn tất.

## 5. Điểm dừng và cách xử lý thiếu dữ liệu

Mặc định report 900–1800 từ; tối đa 15 code files và hai nguồn primary bổ sung. G01 không đọc sâu code; G24/G25 có thể 1800–3000 từ để chứa backlog/traceability. Budget là giới hạn scope nghiên cứu, không quota provider.
Nếu thiếu filesystem/browser/dependency hoặc quá file budget: giữ findings có bằng chứng, ghi phần chưa làm và task followup hẹp, trả PARTIAL/WAITING_INPUT theo rules. Không khắc phục bằng install, login, inference, start server hoặc chỉnh global config.
Xong thì PENDING_REVIEW và dừng; **không tự làm task kế tiếp**. Review fail chỉ sửa đúng phạm vi Gxx, revision tăng, tối đa hai vòng trước khi lead quyết định.

