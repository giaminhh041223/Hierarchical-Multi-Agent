# Sản phẩm và dự án có thể tham khảo

Khảo sát ngày **02/10/2026** bằng repository và tài liệu chính thức. Đây là đánh giá từ tài liệu, chưa cài/chạy thử các sản phẩm. Các đề xuất lựa chọn bên dưới là nhận định thiết kế, không phải kết quả benchmark.

## 1. Các dự án gần với mục tiêu điều phối coding agent local

| Dự án | Phần đã được tài liệu mô tả | Giá trị tham khảo / điều cần kiểm tra |
|---|---|---|
| [Orkestra](https://github.com/andyyaro/orkestra) | Director lập plan; scheduler/DAG và policy bằng code; worktree; kiểm tra và review chéo; SQLite/resume; quyết định cần người dùng; adapter Claude Code, Codex và Antigravity | Rất gần cấu trúc mong muốn. README ghi Windows chưa được thử; bảng adapter chưa liệt kê OpenCode native, có giao thức external để mở rộng. Cần đánh giá adapter và sự cô lập thực tế. |
| [Agent Orchestrator — AO](https://github.com/Untrivial-ai/agent-orchestrator) | Desktop local với project orchestrator, worker riêng, branch/worktree, hội thoại, terminal, diff, PR/CI/review; có bản tải Windows | Ứng viên khảo sát trải nghiệm sử dụng trực tiếp trên máy trước. Repo ComposioHQ cũ chuyển tới repo này; cần kiểm tra đúng release và từng harness muốn dùng. |
| [Stoneforge](https://github.com/stoneforge-ai/stoneforge) | Director, workers, stewards; dispatch theo dependency; worktree; dữ liệu/event bền vững, kênh trao đổi và thư viện tri thức | Tham khảo tổ chức đội ngũ, task pool và bộ nhớ chung. README tự mô tả experimental; mặc định cho agent chạy với permission bypass. Cần đối chiếu với chính sách quyền của dự án. |
| [Vibe Kanban](https://github.com/BloopAI/vibe-kanban) | Board công việc, workspace, terminal/dev server, diff comments, preview và lựa chọn nhiều coding agent | Tham khảo giao diện planning/review. Công ty bloop đóng cửa; dự án tiếp tục open source/community maintained và hướng local. Không mặc định dựa vào dịch vụ remote cũ. [Thông báo chính thức](https://www.vibekanban.com/blog/shutdown) |

Stoneforge có tài liệu hỗ trợ Claude Code, OpenCode và Codex; việc đăng nhập/API key do client tương ứng quản lý, không nhập key tập trung tại Stoneforge. [Multi-provider support](https://docs.stoneforge.ai/guides/multi-provider/)

Kiến trúc Orkestra đáng đọc trực tiếp: [ARCHITECTURE.md](https://github.com/andyyaro/orkestra/blob/main/docs/architecture/ARCHITECTURE.md), [SECURITY_MODEL.md](https://github.com/andyyaro/orkestra/blob/main/docs/SECURITY_MODEL.md). Các bảo đảm trong README cần kiểm chứng bằng code và thử nghiệm theo version; khảo sát này chưa xác minh chúng trên máy người dùng.

## 2. Nền tảng bổ sung cho API, workflow và state

| Thành phần | Khả năng theo tài liệu | Vai trò có thể dùng trong kế hoạch |
|---|---|---|
| [Dify](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose) | Có triển khai self-host; workflow, provider credentials và knowledge retrieval; Human Input cho pause/resume | Tham khảo hoặc sử dụng cho nhánh API workflow, UI kết nối model và bước cần người trả lời. Không suy ra đã có adapter cho mọi coding CLI từ việc hỗ trợ model API. |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | Framework có state, persistence, human-in-the-loop và kết hợp bước bằng code với bước agent | Ứng viên nền engine nếu yêu cầu workflow/resume đủ phức tạp; vẫn cần thiết kế adapter client, workspace và policy. |
| [CrewAI](https://docs.crewai.com/en/concepts/processes) | Process tuần tự hoặc phân cấp; manager model/agent giao việc cho agents | Tham khảo mô hình lead–worker, task context và phối hợp vai trò. Cần đánh giá riêng persistence, CLI integration và budget cho workload thực. |
| [LiteLLM](https://docs.litellm.ai/docs/proxy/virtual_keys) | Gateway API với virtual keys, quyền model và tracking spend; router có load balancing/fallback | Ứng viên lớp API gateway khi có nhiều endpoint/key. Không thay thế scheduler task hoặc cách ly worker sửa code. [Router](https://docs.litellm.ai/docs/routing) |

Dify có [Human Input node](https://dify.ai/blog/the-human-input-node-bringing-human-judgment-into-automated-workflows) và tài liệu [quản lý provider/key](https://docs.dify.ai/en/cloud/use-dify/workspace/model-providers), bao gồm nhiều credential cho một provider. Cần đối chiếu khác biệt cloud/self-host, version và license khi chọn dùng.

Budget của LiteLLM cần deployment có database để được thực thi theo tài liệu; một số kiểm soát chi tiết là tính năng Enterprise. Khi đánh giá phải kiểm tra đúng edition và cấu hình, không suy ra hard cap chỉ từ một dòng config. [Budgets and rate limits](https://docs.litellm.ai/docs/proxy/users)

## 3. Điều chỉnh đề xuất trước khi xây

Phần lead–workers, task dispatch, worktree, review và dashboard đã có nhiều dự án đáp ứng. Nên thêm bước **đánh giá dùng lại hoặc mở rộng** vào giai đoạn 0 trước khi quyết định tự xây toàn bộ.

Thứ tự khảo sát đề xuất:

1. **AO:** kiểm tra trải nghiệm Windows và mức khớp với workflow người dùng.
2. **Orkestra:** đọc engine, adapter Antigravity, recovery và review gates.
3. **Stoneforge:** đối chiếu multi-provider/task pool, communications và knowledge.
4. **Dify/LiteLLM:** đánh giá nhánh API credentials/workflow/usage.
5. **LangGraph/CrewAI:** chọn framework chỉ khi dùng lại làm giảm lượng engine phải sở hữu.

Chưa có bằng chứng trong khảo sát này rằng một sản phẩm bao trọn mọi yêu cầu: automatic client discovery, lựa chọn nguồn quota, môi trường API riêng, Skill Architect tìm/pin/review/phân phối skill, và model routing dựa trên benchmark kết hợp knowledge graph. Đây là các điểm cần kiểm tra từng sản phẩm, không phải khẳng định thị trường chưa có ai làm.

## 4. Bài thử so sánh trước khi chọn nền

- Giao cùng một nhiệm vụ nhỏ, cùng repo/base commit và tiêu chí nghiệm thu.
- Lead chia hai task độc lập; reviewer yêu cầu một lần chỉnh kế hoạch.
- Một task chờ người dùng; task độc lập vẫn tiếp tục.
- Thử lỗi rate limit, thiếu auth, worker crash và restart/resume.
- Kiểm tra giới hạn workspace, quyền tool, thay đổi Git và xử lý conflict.
- Trộn đúng các client cần dùng: Codex, OpenCode, Antigravity; API là một nhánh riêng.
- Đo tổng tokens, số calls, thời gian, thành công, sửa lại và chi phí quan sát được.
- Kiểm tra license, license của dependency, release/support, tài liệu và effort mở rộng.

Sau bài thử mới chọn một trong ba hướng: dùng sản phẩm có sẵn với cấu hình riêng; fork/mở rộng; hoặc xây engine riêng. Giữ UI, scheduler và secret ownership rõ nếu kết hợp nhiều thành phần để tránh hai hệ thống cùng retry hoặc điều phối một task.

Nguồn và câu hỏi đã được đưa vào [research registry](research/SOURCES.md); [bộ task Gemini](research/README.md) yêu cầu pin revision, trace code, kiểm tra contracts và ghi unknown trước khi lập quyết định reuse/fork/build. Các bài thử runtime trên đây vẫn chưa chạy.
