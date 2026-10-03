# Bộ nghiên cứu và giao việc cho Gemini

**Ngày soạn: 02/10/2026. Project: `D:\Hierarchical-Multi-Agent`. Mode: planning/research only.**

Bộ này tổng hợp **49 nguồn** và **26 task G00–G25**. Khi tạo bộ giao việc, tất cả task là **NOT_STARTED** và không điền trước findings/acceptance. Hiện G00 đã được giao qua kênh CLI và có report/review thực; xem tasks.json và [CHANNEL.md](CHANNEL.md) cho trạng thái. Source registry vẫn là khảo sát tài liệu; chưa có code trace pinned hoặc runtime proof của sản phẩm.

## Bắt đầu

**Kênh chạy thử đã được yêu cầu:** xem [CHANNEL.md](CHANNEL.md). Bridge chỉ giao G00 qua Antigravity và thu kết quả cho Codex review; đây là thay đổi phạm vi vận hành kênh, không permission triển khai sản phẩm. Trạng thái task thực xem tasks.json và status của run, không dùng nhãn NOT_STARTED trong task definition làm trạng thái runtime.

Kết quả phiên chạy và review: [SESSION_LOG.md](SESSION_LOG.md). G00 hiện REVISE sau hai correction rounds; G01 chưa được giao.

1. Lead đọc [BRIEF](BRIEF.md) và [kế hoạch kỹ thuật](TECHNICAL_RESEARCH_PLAN.md).
2. Đưa nội dung [START_GEMINI](START_GEMINI.md) cho Gemini tại folder này. Phiên đầu **chỉ G00**.
3. Gemini viết `reports/G00.md` và `results/G00.json`, rồi dừng.
4. Codex/lead/reviewer khác task author dùng [REVIEWER_PROMPT](REVIEWER_PROMPT.md), [checklist](REVIEW_CHECKLIST.md), [review schema](review.schema.json) kiểm tra bằng chứng và đặt decision.
5. Lead chỉ giao task tiếp khi dependencies đã ACCEPT/ACCEPT_WITH_UNKNOWNS. Sau mỗi bước, giao task ID rõ ràng. Không gửi một prompt “làm hết G00–G25”.

Phải kiểm soát quyền thực bằng host/tool policy. Các luật prompt và schema hỗ trợ phát hiện lỗi, không ngăn được mọi hallucination hoặc filesystem write. Không có automation hay enforcement runtime đã xây trong bộ tài liệu này.

## File cần dùng

| File | Vai trò |
|---|---|
| [SOURCES.md](SOURCES.md) / [sources.json](sources.json) | Nhóm nguồn, câu hỏi nghiên cứu, retrieval status, recheck requirement |
| [BRIEF.md](BRIEF.md) | Yêu cầu user vs exploratory/inspiration vs đề xuất chưa chốt |
| [GEMINI_RULES.md](GEMINI_RULES.md) | Evidence levels, scope, quyền, giới hạn, điểm dừng |
| [tasks.json](tasks.json) | Manifest giao việc/dependencies/outputs/acceptance IDs; chưa phải scheduler |
| [tasks/](tasks/) | Task chi tiết: steps, nguồn, output paths, acceptance, stop |
| [REPORT_TEMPLATE.md](templates/REPORT_TEMPLATE.md) | Report có claim IDs và unknowns |
| [RESULT.template.json](templates/RESULT.template.json) / [result.schema.json](result.schema.json) | Mẫu và schema output Gemini; không phải research result thật |
| [REVIEWER_PROMPT.md](REVIEWER_PROMPT.md) / [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) | Review độc lập và chặn unsupported claims |
| [review.schema.json](review.schema.json) | Decision gắn revision/hash result, quyền ghi chỉ reviewer |

Các thư mục `reports/`, `results/`, `reviews/` được tạo khi có output thật; không điền findings hay ACCEPT giả để làm đẹp trạng thái. `.research/` là source-only cache cho G01 tương lai, không chứa credentials và không execute.

## Giai đoạn và điều kiện chuyển bước

| Giai đoạn | Tasks | Câu hỏi phải giải quyết | Gate |
|---|---|---|---|
| 0. Baseline & sources | G00–G01 | Cái gì là yêu cầu thật? Nguồn/version nào dùng được? | Yêu cầu phân loại; revision/failed-source rõ |
| 1. Reference internals | G02–G08 | Scheduler/state/recovery/permissions/workspaces thật hoạt động theo code nào? | Trace và conflicts được review; code chưa pin không dùng |
| 2. Integration contracts | G09–G15 | CLI/server/account/API khác nhau ra sao? Dùng gateway/framework phần nào? | Fields có official evidence hoặc UNKNOWN |
| 3. Proposed system design | G16–G22 | Interface/state/quyền/context/skills/model registry/budgets nối thế nào? | Một owner cho state/retry; unknown không biến thành fact |
| 4. Decision & handoff | G23–G25 | Reuse/fork/build có điều kiện gì? Implement task nào sau? | Lead review tradeoffs, backlog và evidence traceability |

UNKNOWN được phép trong nghiên cứu nhưng critical unknown không được bỏ qua để quyết định deployment. ACCEPT_WITH_UNKNOWNS phải ghi allowed downstream assumptions và scope chưa chứng minh. Cần experiment có quyền để chốt runtime; chưa authorize trong hiện tại.

## Danh sách task

| ID | Giao việc | Dependencies |
|---|---|---|
| G00 | [Chốt yêu cầu và ranh giới nghiên cứu](tasks/G00-baseline.md) | — |
| G01 | [Xác minh và khóa nguồn tham khảo](tasks/G01-source-lock.md) | G00 |
| G02 | [Truy vết engine và recovery của Orkestra](tasks/G02-orkestra-engine.md) | G01 |
| G03 | [Bóc tách adapter, workspace và review gates Orkestra](tasks/G03-orkestra-boundaries.md) | G01, G02 |
| G04 | [Truy vết điều phối và sessions của Agent Orchestrator](tasks/G04-ao-engine.md) | G01 |
| G05 | [Đánh giá AO trên Windows và discovery tài nguyên](tasks/G05-ao-platform.md) | G01, G04 |
| G06 | [Bóc tách roles, dispatch và persistent knowledge Stoneforge](tasks/G06-stoneforge-engine.md) | G01 |
| G07 | [Bóc tách provider, review và permissions Stoneforge](tasks/G07-stoneforge-policy.md) | G01, G06 |
| G08 | [Audit chéo bằng chứng và khoảng trống các sản phẩm](tasks/G08-reference-audit.md) | G02, G03, G04, G05, G06, G07 |
| G09 | [Contract tích hợp Codex local](tasks/G09-codex-contract.md) | G01, G08 |
| G10 | [Contract Antigravity cho Claude và Gemini](tasks/G10-antigravity-contract.md) | G01, G08 |
| G11 | [Contract OpenCode CLI và server](tasks/G11-opencode-contract.md) | G01, G08 |
| G12 | [Bóc tách contract API model độc lập](tasks/G12-api-contracts.md) | G01, G08 |
| G13 | [Phân tích Dify cho API credentials và human workflow](tasks/G13-dify-workflow.md) | G01, G08 |
| G14 | [Phân tích gateway, routing và budgets LiteLLM](tasks/G14-litellm-gateway.md) | G01, G08 |
| G15 | [Đánh giá hẹp LangGraph và CrewAI](tasks/G15-framework-choice.md) | G01, G08 |
| G16 | [Thiết kế contract adapter chung và capability registry](tasks/G16-common-adapter.md) | G09, G10, G11, G12 |
| G17 | [Thiết kế state machine, DAG và recovery](tasks/G17-scheduler-design.md) | G02, G04, G06, G08, G15, G16 |
| G18 | [Thiết kế workspace, process policy và credential vault Windows](tasks/G18-windows-isolation.md) | G03, G05, G07, G09, G10, G11, G16 |
| G19 | [Thiết kế context, kênh trao đổi và knowledge tối thiểu](tasks/G19-context-knowledge.md) | G06, G16, G17 |
| G20 | [Thiết kế Skill Architect và phân phối skills/plugins](tasks/G20-skill-architect.md) | G00, G01, G16, G18 |
| G21 | [Thiết kế registry benchmark và lựa chọn model](tasks/G21-model-intelligence.md) | G00, G01, G16 |
| G22 | [Thiết kế budgets, resource pools và telemetry](tasks/G22-budget-observability.md) | G14, G16, G17, G19, G21 |
| G23 | [Lập quyết định dùng lại, fork hoặc tự xây có bằng chứng](tasks/G23-reuse-decision.md) | G08, G13, G14, G15, G16, G17, G18, G19, G20, G21, G22 |
| G24 | [Bản thiết kế kỹ thuật và backlog triển khai sau nghiên cứu](tasks/G24-implementation-plan.md) | G23, G16, G17, G18, G19, G20, G21, G22 |
| G25 | [Audit bàn giao và ma trận truy xuất bằng chứng](tasks/G25-handoff-audit.md) | G24, G00, G01, G08, G09, G10, G11, G12, G13, G14, G15, G16, G17, G18, G19, G20, G21, G22, G23 |

Dependency DAG thể hiện task nào có thể độc lập; mặc định vẫn giao từng task. Nếu muốn parallel sau này lead phải phân scope/output và reviewer rõ, Gemini không tự spawn. Không có requirement chọn model mạnh nhất bằng tên: người dùng chọn nguồn/model; registry chỉ hỗ trợ quyết định có bằng chứng.

## Cách giữ context nhỏ mà còn truy xuất được

Mỗi lần giao: BRIEF+RULES+task, vài claim extracts cần thiết của dependencies, source-lock locators, reviewer decision. Không tải cả 49 trang hoặc toàn bộ repo vào một context. Output report/result bền vững, source snapshots pinned; lead đưa summary có refs. Facts/decisions/unknowns được giữ, không lưu chain-of-thought.

Target report 900–1800 từ; G24/G25 có thể 1800–3000. Tối đa 15 code files/task, hai primary sources bổ sung. Nếu scope cần hơn, PARTIAL cùng task followup nhỏ; không tự tăng scope.

G01 lập manifest 49 entries nhưng revision đầu chỉ pin bốn repo và recheck tối đa tám trang contract ưu tiên. Các nguồn còn lại giữ NOT_RECHECKED; task downstream recheck đúng nguồn nó sử dụng. Registry đầy đủ không đồng nghĩa 49 trang đã được xác minh lại trong một task.

## Bảo toàn phạm vi

Hiện tại không install, login, đọc key/auth store, inference, start server, run remote repo code, commit/push/merge hay sửa app. G09–G11 chỉ cho version/help metadata theo allowlist. G01 cho lấy source-only cache, không build.

Historical local versions trong INTEGRATIONS.md không tự coi còn đúng. Tài liệu source đã đọc không chứng minh account authenticated, quota available hay inference successful. Dự thảo Python/UI trước đây chưa nghiệm thu, không được dùng làm bằng chứng app chạy.

Khi tương lai được authorize triển khai, lead duyệt riêng blueprint/backlog G24 và các runtime experiments còn thiếu; research acceptance không phải permission deploy hoặc dùng tài khoản.

