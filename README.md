> **Code đang phát triển nằm ở [`prototype/`](prototype/README.md)** (Orchestra: engine, CLI, web UI, test). Phần còn lại của thư mục gốc dưới đây là bộ đề xuất và mã nháp do Codex viết trước đó, giữ lại để tham khảo, chưa tích hợp với prototype.

# Agent Orchestra — bản đề xuất dự án

**Trạng thái ngày 03/10/2026: khảo sát và lập kế hoạch.** Công việc triển khai sản phẩm đã dừng. Một số file Python và giao diện được tạo trước khi đổi phạm vi là **mã nháp chưa tích hợp**, không phải một ứng dụng đã nghiệm thu. Theo yêu cầu mới, kênh nghiên cứu riêng đã gọi Gemini Flash 3.8 High qua Antigravity để làm G00; chưa thử inference trong app nháp hoặc bằng API key độc lập.

## Đọc theo thứ tự

1. [Kế hoạch sản phẩm](docs/PRODUCT_PLAN.md): phạm vi, trải nghiệm người dùng, quyết định kiến trúc và thứ tự phát triển.
2. [Kiến trúc chi tiết](docs/ARCHITECTURE.md): roles, scheduler, workspace, context, credentials, knowledge và benchmarks.
3. [Khảo sát tích hợp](docs/INTEGRATIONS.md): Codex, OpenCode, Antigravity/Claude/Gemini, Z.AI và API độc lập; bằng chứng và giới hạn.
4. [Lộ trình & nghiệm thu](docs/ROADMAP.md): các giai đoạn, kiểm thử chấp nhận và điều kiện chuyển bước.
5. [Sản phẩm hiện có](docs/EXISTING_PRODUCTS.md): các dự án gần mục tiêu, nền tảng API/workflow và bài thử để chọn dùng lại, mở rộng hoặc tự xây.
6. [Bộ nghiên cứu giao Gemini](docs/research/README.md): 49 nguồn, 26 task hẹp, mẫu đầu ra và review độc lập. Bắt đầu bằng [prompt G00](docs/research/START_GEMINI.md); chưa triển khai ứng dụng.

Tài liệu là đề xuất để thảo luận trước khi bắt tay xây. Các tiêu chí nghiệm thu trong roadmap chưa được đánh dấu hoàn tất.

Theo yêu cầu mới, đã thêm [kênh local Codex ↔ Gemini](docs/research/CHANNEL.md)
để giao G00 và kiểm tra output. Kênh nghiên cứu tách khỏi app nháp; trạng thái và
kết quả của mỗi lần gọi có logs riêng.

