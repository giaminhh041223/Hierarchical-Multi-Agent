# Lộ trình ĐỀ XUẤT và tiêu chí nghiệm thu

Cập nhật ngày **02/10/2026 — PLAN ONLY**. Theo yêu cầu mới nhất, triển khai đã dừng; mã nháp tạo trước đó chưa được tích hợp/nghiệm thu. Tất cả checkbox bên dưới là tiêu chí tương lai, không phải tính năng đã bàn giao. [PRODUCT_PLAN.md](PRODUCT_PLAN.md) là bản đề xuất sản phẩm chính; tài liệu này chi tiết hoá các giai đoạn 0–5.

## Giai đoạn 0 — Chốt thiết kế và tài nguyên

Dùng [bộ nghiên cứu giao Gemini](research/README.md) để thực hiện khảo sát có kiểm soát: nguồn/version → reference code → client/API contracts → thiết kế → quyết định/backlog. 26 task đang NOT_STARTED; review nghiên cứu không tự authorize triển khai hoặc inference.

- [ ] Chốt loại nhiệm vụ mẫu, tiêu chí chất lượng và baseline một agent.
- [ ] Đánh giá dùng lại/mở rộng AO, Orkestra hoặc Stoneforge bằng cùng scenario; đối chiếu API layer Dify/LiteLLM và framework LangGraph/CrewAI trước khi quyết định tự xây. Xem [EXISTING_PRODUCTS.md](EXISTING_PRODUCTS.md).
- [ ] Tách client/runtime, provider, account/connection, model, role và environment trong schema.
- [ ] Chọn provider/model theo vai trò sau discovery; installed/catalog/auth/inference có nhãn bằng chứng riêng.
- [ ] Chốt quyền tự sửa trong workspace và phạm vi phải đưa về người dùng.
- [ ] Chốt budget, quota group, timeout, concurrency và cách đo usage.
- [ ] Chốt task/result/event schema, revision, retry và reconciliation trước khi build.
- [ ] Chốt phương án worker isolation Windows và nơi lưu secret; không coi working directory là sandbox.

**Cổng nghiệm thu:** có scenario đầu đến cuối, capability matrix và quyết định thiết kế đủ để ước lượng phạm vi triển khai. Khảo sát CLI hiện tại là đầu vào, chưa tự hoàn tất giai đoạn này.

## Giai đoạn 1 — Engine và bản thử nghiệm local

**Mục tiêu:** kiểm chứng việc điều phối bằng demo trước khi bật inference thật. Đây là phạm vi MVP được đề xuất.

### Workflow và trạng thái

- [ ] Chạy một lệnh local trên Windows để mở dashboard; server bind loopback.
- [ ] Tạo run từ mục tiêu và lựa chọn provider/model theo role.
- [ ] Run giữ snapshot cấu hình; đổi cấu hình chung không đổi run đã tạo.
- [ ] Workflow có lead planner → reviewer và skill architect song song → worker theo DAG hữu hạn → final reviewer → lead synthesis.
- [ ] Plan sai schema, có cycle, quá nhiều task hoặc dependency không tồn tại bị từ chối với lỗi dễ xử lý.
- [ ] Demo thể hiện một worker `waiting_human` trong khi worker độc lập vẫn hoàn tất.
- [ ] Người dùng retry, complete thủ công hoặc cancel task đang chờ; dependency chưa thỏa không tự chạy.
- [ ] Retry có trần theo loại lỗi; giao diện phân biệt retry và tổng attempts. Giá trị khởi điểm đề xuất là 3 retry, cần đánh giá.
- [ ] Khởi động lại giữ task/event/artifact; task đang chạy chuyển thành cần người dùng xử lý.
- [ ] Task bị cancel khiến nhánh phụ thuộc bị chặn; nhánh độc lập không bị hủy theo.

### Context, workspace và tri thức

- [ ] Mỗi task có folder riêng cùng `AGENTS.md` và `CONTEXT.md`.
- [ ] Context có trần và ưu tiên mục tiêu task, dependency summary, knowledge liên quan.
- [ ] Token hiển thị có nhãn ước lượng; không hiển thị như usage billing chính thức.
- [ ] Có preflight budget check và kiểm tra sau output; tài liệu ghi giới hạn hard cap.
- [ ] Skill architect phân phối skill builtin local và giải thích skill phù hợp task nào.
- [ ] Knowledge node/cạnh được lưu SQLite; worker nhận tập thông tin liên quan có giới hạn.
- [ ] Benchmark manual import giữ model/suite/score/source/date, không có điểm mẫu giả làm dữ liệu thật.

### Kết nối và an toàn tối thiểu

- [ ] Discovery chỉ chạy lệnh metadata phù hợp; không đọc key/cookie để đoán tài khoản.
- [ ] Installed, catalog, auth và inference verified được hiểu là các mức bằng chứng riêng.
- [ ] API key nhập qua UI chỉ tồn tại trong RAM; endpoint trạng thái không trả plaintext.
- [ ] Key không xuất hiện trong SQLite, log, file artifact hoặc Git.
- [ ] API mutation kiểm tra Host/Origin và token phiên; website ngoài không gọi được hành động local.
- [ ] Adapter API từ chối absolute path, traversal, symlink/junction thoát workspace và output quá lớn.
- [ ] Adapter CLI có timeout theo policy (180 giây là giá trị khởi điểm đề xuất) và mức quyền thể hiện đúng với khả năng runtime.
- [ ] Demo và provider thật luôn có nhãn; thiếu auth không âm thầm chuyển sang kết quả demo.

**Cổng nghiệm thu:** bộ kiểm tra tự động nhỏ bao phủ scheduler/resume, validation và các trust boundary quan trọng; một lần chạy demo có bằng chứng chờ người dùng nhưng sibling hoàn tất. Không cần gọi trả phí để chứng minh scheduler. Khi chưa có inference thật, tài liệu nói rõ adapter mới được xác minh đến metadata/protocol.

## Giai đoạn 2 — Kết nối client, API và môi trường

**Mục tiêu:** kiểm chứng từng connector bằng task hẹp, sau đó chạy phối hợp nhiều provider. Codex, OpenCode, Antigravity và các API là các nguồn tài nguyên chính trong kế hoạch.

- [ ] Người dùng chọn rõ tài khoản/provider/model; login thực hiện qua luồng chính thức.
- [ ] Smoke test có sự cho phép sử dụng tài nguyên, ghi model thực tế và kết quả thành công; không ghi secret.
- [ ] Kiểm tra output JSON/stream của đúng version CLI cài trên máy; malformed output không được coi là thành công.
- [ ] Xác minh sandbox trên Windows bằng thử ghi bên ngoài workspace trong môi trường test an toàn; connector không tự hạ quyền bảo vệ khi test thất bại.
- [ ] Hoàn tất task nhỏ: tạo file trong workspace, kiểm tra nội dung bằng validator xác định, reviewer đưa bằng chứng và lead tổng hợp đường dẫn artifact.
- [ ] Phân biệt lỗi auth, rate limit, provider timeout, budget, output và policy để người dùng xử lý đúng việc.
- [ ] Có cơ chế hủy subprocess và xử lý subprocess con phù hợp nền tảng; không để tool vẫn chạy sau khi UI báo canceled.
- [ ] Usage chính thức, nếu API trả về, được giữ riêng với estimate; thiếu usage là unknown.
- [ ] Codex, OpenCode và Antigravity có capability/auth/isolation gate riêng, ánh xạ lỗi, session và cancel/resume theo version thực tế.
- [ ] Antigravity thử Claude và Gemini theo lựa chọn/quyền tài khoản; catalog không được tính là inference thành công.
- [ ] OpenCode có project/account profile và server scope rõ; không tự dùng chung session đa dự án.
- [ ] API adapter phân biệt OpenAI Responses, compatible Chat Completions, Anthropic Messages, Gemini và endpoint/gói Z.AI.
- [ ] Connection profile có endpoint, auth/secret reference, model allowlist, timeout, quota group, rate/concurrency và budget.
- [ ] Environments dev/test/prod có secret binding và policy riêng; key thiếu không fallback key global/dev.
- [ ] Process worker chỉ nhận biến cần thiết; không kế thừa mọi secret của server.
- [ ] Endpoint từ xa dùng TLS verification, redirect không chuyển key sang host khác, log/export không chứa secret.
- [ ] API workflow hẹp gồm input → retrieval → model → validation → artifact; tool call chỉ chạy qua host policy.
- [ ] Lỗi schema/test được worker/lead xử lý hữu hạn; rate limit chuyển waiting_resource; thiếu auth/quyền/budget chuyển Inbox.

**Cổng nghiệm thu:** có ít nhất một run với provider thật, một lỗi có thể resume, artifact đúng tiêu chí và chứng cứ mức cô lập. Không suy rộng từ một adapter sang mọi CLI khác.

## Giai đoạn 3 — Planning, repository và bàn giao

**Mục tiêu:** các worker sửa mã nguồn đồng thời mà không ghi đè nhau hoặc làm mất thay đổi của người dùng.

- [ ] Lead và reviewer chỉnh plan tối đa hai vòng theo mặc định đề xuất; lưu version, phản biện và lý do thay đổi.
- [ ] Lead xử lý lỗi trong phạm vi đã giao; chỉ thiếu thông tin hoặc vượt quyền mới hỏi người dùng.
- [ ] Mọi task có skill manifest; Skill Architect tái sử dụng pack đã review khi phù hợp.
- [ ] Chọn repository và ghi nhận Git status trước khi chạy; bảo toàn thay đổi chưa commit.
- [ ] Tạo worktree riêng cho task ghi code; giữ base commit, branch/task ownership và artifact diff.
- [ ] Planner chia phạm vi file/module; scheduler phát hiện task có khả năng ghi trùng vùng.
- [ ] Reviewer đọc diff và kết quả test thực tế; không chỉ đọc lời tự báo cáo của worker.
- [ ] Test chạy bằng command được cấu hình/ủy quyền với timeout và log đã lọc secret.
- [ ] Hợp nhất vào integration worktree theo thứ tự dependency; conflict thành task cần giải quyết.
- [ ] Merge vào checkout chính hoặc push/PR tuân theo quyền người dùng đã giao; luôn có kết quả cụ thể để review.
- [ ] Recovery không xóa worktree có output chưa được giữ lại; có thao tác dọn dẹp rõ ràng.
- [ ] Side effect ngoài Git có idempotency/reconciliation trước retry.

**Cổng nghiệm thu:** hai worker sửa hai phần độc lập, một trường hợp conflict, một trường hợp test fail; hệ thống giữ nguyên checkout ban đầu cho đến bước tích hợp được cho phép.

## Giai đoạn 4 — Skill registry và bộ nhớ dùng chung

**Mục tiêu:** tìm/chọn skill từ nguồn ngoài mà vẫn biết nguồn gốc và quyền thực thi.

- [ ] Registry lưu repository, owner, đường dẫn, commit pin, license, loại skill/plugin/MCP và quyền cần dùng.
- [ ] Search trả về nguồn có URL và ngày tra cứu; không dựa số sao làm bằng chứng an toàn/chất lượng.
- [ ] Review `SKILL.md`, manifest, install script và diff update trước khi đưa vào pack dùng chung.
- [ ] Cài vào phạm vi dự án/worker; không ghi đè skill toàn máy khi không được yêu cầu.
- [ ] Chính sách nguồn được cho phép và quyền được cấp giúp tái sử dụng an toàn, tránh hỏi lại cho cùng phạm vi đã phê duyệt.
- [ ] Skill không được tự cấp quyền truy cập credential, network hoặc filesystem chỉ bằng instruction.
- [ ] Thử skill trên task mẫu; giữ kết quả trước/sau để chứng minh nó cải thiện đầu ra.
- [ ] Có pin version, rollback và gỡ pack không còn dùng.
- [ ] Knowledge record có provenance, project/environment scope, ngày cập nhật và hiệu lực.
- [ ] Mỗi cạnh suy ra được đánh dấu riêng với cạnh có bằng chứng; truy được về source artifact.
- [ ] Retrieval lọc quyền trước khi text/entity/edge lookup; secret không được đưa vào knowledge graph.
- [ ] Mỗi task có manifest riêng hoặc tham chiếu pack chung; không phải tìm GitHub/gọi model lại nếu pack hợp lệ đã có.

**Cổng nghiệm thu:** thêm một skill từ GitHub bằng commit cố định, review được nguồn và diff, phân phối đúng role, rollback được, và chặn một skill yêu cầu quyền ngoài policy.

## Giai đoạn 5a — Đánh giá retrieval và chọn model theo dữ liệu

**Mục tiêu:** chọn model và context theo bằng chứng, đo được hiệu quả với dự án thực.

- [ ] Knowledge record có provenance, project scope, ngày cập nhật và trạng thái có còn hiệu lực.
- [ ] Mỗi cạnh suy ra được đánh dấu riêng với cạnh đã có bằng chứng; có thể truy về nguồn.
- [ ] Tạo một tập câu hỏi/task mẫu để đo truy hồi: độ đúng, thông tin thiếu, thời gian và lượng context.
- [ ] Chỉ thêm FTS/vector/GraphRAG khi có failure case mà truy hồi văn bản hiện tại không xử lý được.
- [ ] Benchmark giữ model snapshot, suite/version, setup, ngày chạy, nguồn và điều kiện cost/latency.
- [ ] Không gộp điểm các suite khác nhau thành bảng xếp hạng chung không có phương pháp.
- [ ] Eval local có task domain, tiêu chí tự động và review của người dùng cho mẫu khó.
- [ ] Router tôn trọng model user chọn, auth/availability, budget và quyền; giải thích vì sao đề xuất đổi model.
- [ ] Theo dõi baseline cố định để chứng minh context pack/caching/model routing có tiết kiệm thực tế.
- [ ] Có ngưỡng stale và yêu cầu cập nhật dữ liệu; không tự xem benchmark cũ là năng lực hiện tại.

**Cổng nghiệm thu:** so sánh với baseline trên cùng bộ task, báo tỷ lệ thành công, chi phí khi quan sát được, thời gian và độ biến thiên. Không kết luận “tối ưu” từ một demo.

## Giai đoạn 5b — Workflow editor và vận hành dài hạn

**Mục tiêu:** mở rộng sau khi workflow cố định đã đáng tin.

- [ ] Workflow editor tạo DAG hợp lệ và preview quyền/ngân sách trước run.
- [ ] Workflow template có version, input schema và migration; lưu được cấu hình để tái chạy.
- [ ] Nodes có kiểu cho LLM, agent, tool/function, retrieval, validation, routing và human input; không eval code do model tự viết để route.
- [ ] Chuyển environment đòi ánh xạ connection/secret/policy rõ, không sao chép key trong file template.
- [ ] n8n nếu tích hợp chỉ gửi/nhận run qua API; engine vẫn sở hữu task lifecycle và tránh retry kép.
- [ ] Native notification hoặc kênh ngoài gửi đúng sự kiện cần xử lý; không spam các run không đổi.
- [ ] Vault Windows dùng Credential Manager/DPAPI với chính sách lifecycle rõ; key không trả lại frontend.
- [ ] Thêm user/session auth thực trước khi cho bind LAN; localhost token không được quảng bá như hệ thống multi-user.
- [ ] Có audit/export/redaction/retention và khôi phục bản sao lưu.
- [ ] Chỉ chuyển sang worker service/message broker khi throughput hoặc cách ly process chứng minh cần thiết.

**Cổng nghiệm thu:** một người dùng tạo được workflow từ UI, chạy lại và xử lý lỗi bằng hướng dẫn trong sản phẩm; trạng thái và artifact có thể được khôi phục từ bản sao lưu.

## Các quyết định chưa chốt bằng cảm tính

| Câu hỏi | Mặc định MVP | Bằng chứng cần để thay đổi |
|---|---|---|
| Có cần graph database riêng? | SQLite node/edge + text retrieval | Dữ liệu và query thực cho thấy latency/khả năng truy hồi không đạt |
| Có cần nhiều lead? | Một lead, reviewer phản biện tối đa hai vòng theo đề xuất | Eval cho thấy một hội đồng cải thiện đủ để bù token/latency |
| Có cần mỗi task tự tìm skill mới? | Dùng builtin/catalog trước | Skill mới giải được failure case cụ thể và qua review |
| Có tự chọn “model mạnh nhất”? | Người dùng chọn theo role | Benchmark cùng setup + eval dự án + entitlement thực |
| Có chạy tự động mọi CLI được tìm thấy? | Chỉ adapter đã kiểm tra quyền/protocol | Tài liệu và smoke test version cụ thể chứng minh hỗ trợ |
| Có lưu API key lâu dài? | RAM-only | Người dùng cần persistence và vault được triển khai/kiểm thử |
| Có hard token/cost cap? | Ước lượng có cảnh báo giới hạn | Provider quota hoặc quyền kiểm soát đầy đủ request và usage |

Thứ tự đề xuất: **chốt thiết kế → scheduler và recovery → từng connector/API environment → planning và repository/worktree → skill/memory → eval/routing/workflow canvas**. Các luồng 5a/5b có thể ưu tiên lại dựa trên nhu cầu thực. Chưa ấn định lịch triển khai hoặc chi phí trước khi chốt scope và tài nguyên.
