# Brief cố định cho nghiên cứu Gemini

Ngày: **02/10/2026**. Mục tiêu hiện tại: nghiên cứu, bóc tách kỹ thuật và chuẩn bị kế hoạch để lead quyết định dùng lại/mở rộng/tự xây. **Không triển khai sản phẩm hoặc chạy inference.**

## Yêu cầu từ người dùng

| ID | Nội dung | Loại |
|---|---|---|
| RQ01 | Môi trường điều phối agent local trong một folder/project | USER_REQUIREMENT |
| RQ02 | Lead nhận yêu cầu trực tiếp, thường là model mạnh nhất người dùng chọn | USER_REQUIREMENT |
| RQ03 | Phát hiện client/agent khả dụng và cho người dùng chọn model | USER_REQUIREMENT |
| RQ04 | Codex, OpenCode, Claude/Gemini qua Antigravity; xem xét Z.AI | USER_REQUIREMENT |
| RQ05 | Lead thảo luận với reviewer để lên plan lớn trước khi phân task | USER_REQUIREMENT |
| RQ06 | Rule riêng cho worker và kênh trao đổi có cấu trúc | USER_REQUIREMENT |
| RQ07 | Tối ưu context, token, thời gian trong tiêu chí chất lượng | USER_REQUIREMENT |
| RQ08 | Lead xử lý lỗi trong quyền; vượt quyền đưa về người dùng | USER_REQUIREMENT |
| RQ09 | Task pending chờ phản hồi; task độc lập vẫn tiếp tục | USER_REQUIREMENT |
| RQ10 | Khu vực kết nối API key, cấu hình môi trường và workflow API | USER_REQUIREMENT |
| RQ11 | Luồng đăng nhập account chính thức của client/agent | USER_REQUIREMENT |
| RQ12 | Worker tự làm/sửa file trong scope project được giao khi triển khai | USER_REQUIREMENT |
| RQ13 | Skill Architect tìm/chọn skill GitHub/plugin và phân phối phù hợp task | USER_REQUIREMENT |
| RQ14 | Thông tin benchmark năng lực model có sẵn để hỗ trợ lead | USER_EXPLORATORY |
| RQ15 | Knowledge graph/kết nối tri thức nếu giúp hiệu quả và tài nguyên | USER_EXPLORATORY |
| RQ16 | Tham khảo trải nghiệm n8n | USER_INSPIRATION |
| RQ17 | Tổng hợp sản phẩm hiện có, nguồn và bóc tách kỹ thuật chi tiết | CURRENT_DELIVERABLE |
| RQ18 | Task Gemini phải hẹp, chi tiết, có bằng chứng và điểm dừng | CURRENT_CONSTRAINT |

## Đề xuất trước đó chưa phải quyết định đã chốt

Windows một người dùng trước; Python stdlib/SQLite/vanilla UI; RAM-only prototype hoặc vault Windows; tối đa hai vòng review plan; một số vòng retry; graph có typed edges + FTS trước; Git worktree; n8n làm ingress. Tất cả phải đánh dấu PROPOSED, được đánh giá lại theo nguồn và nhu cầu. Không được ghi rằng người dùng đã chọn stack, provider/model cụ thể, tổng budget hay SLA.

## Bằng chứng local lịch sử

Khảo sát trước ghi Codex 0.153.4, OpenCode 1.17.7, Antigravity 1.2.14 và catalog Claude/Gemini. Đó là historical observations trong docs/INTEGRATIONS.md, cần recheck nếu dùng để thiết kế contract. Chưa có bằng chứng auth/inference/quota. File orchestra.py, adapters.py và web/ là draft tạo trước khi phạm vi đổi; không phải reference implementation đã nghiệm thu. G00 chỉ cần đánh dấu trạng thái đó, không audit/hoàn thiện code nháp.

## Đầu ra nghiên cứu cần chốt

Các claim có nguồn/version; code flow và state machine; client/API contracts; quyền/workspace/secret; context/skill/knowledge/budget; capability gaps và lựa chọn build/fork/reuse; backlog triển khai từng bước với kiểm thử nghiệm thu. Khi chưa đủ bằng chứng, kết luận có thể là NOT_EVALUATED và đề xuất bài thử tiếp theo.

## Giới hạn hiện tại

Đọc tài liệu/source và lệnh metadata an toàn theo task. Chỉ viết report/result/snapshot được task cho phép. Không chạy code từ repo ngoài, cài package/plugin/skill, sửa runtime/settings global, login, đọc secret, gọi model trả phí, mở server, Git commit/push/merge hay thay đổi sản phẩm.

