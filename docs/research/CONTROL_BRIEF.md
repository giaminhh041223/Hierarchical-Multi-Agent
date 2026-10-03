# Chỉ thị vận hành kênh hiện tại

Ngày 02/10/2026, người dùng đã yêu cầu Codex tạo kênh giao tiếp và gọi Gemini
thực hiện nghiên cứu. Sau đó người dùng chọn rõ **Gemini Flash 3.8 High**:
slug CLI đã xuất hiện trong catalog là gemini-3.8-flash-high.

Quyết định này áp dụng cho research worker đang được gọi, chưa chọn model cho
lead/reviewer/worker pool của sản phẩm tương lai. Scope sản phẩm vẫn planning-only.
Lead được chạy phiên Gemini và kiểm/review/lưu artifacts; worker không được gọi
model khác, install, sửa app, đọc auth store hoặc thực hiện runtime experiments.

Host gửi inputs qua packet. Worker không đọc filesystem hoặc chạy commands.
Tool finish nếu CLI yêu cầu để kết thúc response được phép chỉ cho lifecycle/
bàn giao theo tool schema CLI cung cấp; không dùng tool khác.
Host stream monitor không OS sandbox hay pre-execution interceptor.

BRIEF thắng các tài liệu nháp khi xác định phạm vi planning. Chỉ thị mới trực tiếp
từ user và host/tool policy vẫn có ưu tiên cao hơn; không coi BRIEF là luật tuyệt đối.

G00 revisions 1 và 2 đã được Codex review REVISE. Revision 3 chỉ sửa các corrections
trong reviews/G00.json, giữ task G00 và dừng. Đây là vòng sửa cuối trong giới hạn
hai correction rounds; G01 chưa được giao.
