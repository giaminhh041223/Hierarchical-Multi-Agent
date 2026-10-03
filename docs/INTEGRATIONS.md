# Kết nối provider: bằng chứng và giới hạn

Kiểm tra ngày **02/10/2026**, múi giờ Asia/Saigon. Đây là kết quả tại máy hiện tại, không phải cam kết mọi tài khoản đều được dùng model đó. Không đọc file credentials, không lấy token từ client, không đăng nhập mới và không chạy inference trả phí trong quá trình kiểm tra.

**Trạng thái theo yêu cầu mới:** ưu tiên xem xét và lập kế hoạch, đã dừng viết/chạy code. Các file adapter và test đã tạo trước khi có chỉ dẫn mới được giữ như bản nháp nghiên cứu, chưa phải ứng dụng hoàn chỉnh. Nội dung bên dưới phân biệt discovery đã làm, bản nháp đã có và thiết kế còn cần quyết định.

## Ma trận hỗ trợ

| Provider/client | Bằng chứng trên máy | Giao diện chính thức | Hướng tích hợp đề xuất |
|---|---|---|---|
| Codex CLI | `codex-cli 0.153.4`, kiểm tra help thành công | `exec` JSONL; App Server | Execution host chính, task workspace và policy riêng |
| OpenCode | `1.17.7`, kiểm tra help thành công | `run --format json`; HTTP server | Execution host chính đa provider; session/approval/event API |
| Google Antigravity | `agy 1.2.14`; `agy models` thành công | Headless JSON/JSONL; SDK Python | Execution host chính cho Claude/Gemini qua account, sau kiểm tra isolation |
| OpenAI API | Chưa kiểm tra tài khoản | Responses API | Adapter native riêng; không ép mọi model qua Chat Completions |
| Z.AI | Không yêu cầu client riêng | HTTP Chat Completions; connector OpenCode | API adapter hoặc qua OpenCode, đúng loại key/gói/endpoint |
| Anthropic API | Không kiểm tra tài khoản | Messages API | Adapter API riêng |
| Gemini API | Không kiểm tra tài khoản | `generateContent` | Adapter API riêng |

Đây là bảng thiết kế, chưa có orchestration hoàn chỉnh được nghiệm thu. “Discovery” chỉ đọc đường dẫn, version và catalog; auth vẫn chưa xác minh. Bản nháp hiện có chưa triển khai mọi hướng trong bảng.

## Codex

CLI chính thức hỗ trợ chạy tác vụ không tương tác và JSONL. Thiết kế adapter kiểm tra `turn.completed` trước khi nhận kết quả, lấy usage nếu provider trả về. Tác vụ dự kiến sử dụng `workspace-write`, approval policy `never`, task directory riêng; không dùng bypass sandbox. [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)

Lệnh tương đương của adapter:

```text
codex exec --json --sandbox workspace-write --ignore-user-config -c approval_policy="never" --skip-git-repo-check -C <task-directory> --model <selected-model> -
```

Prompt truyền qua stdin. Trên Windows, adapter tìm executable thật thay cho việc truyền prompt qua npm `.cmd` và shell. Không cần tạo shell script từ nội dung model.

Codex hỗ trợ đăng nhập ChatGPT hoặc API key với cơ chế sử dụng và quản trị khác nhau. CLI tự sử dụng login đã lưu; ứng dụng này không sao chép file auth. Người dùng đăng nhập bằng client chính thức khi cần. API Platform là kết nối riêng, không mặc định lấy quota ChatGPT. [Authentication](https://learn.chatgpt.com/docs/auth)

Giai đoạn sau có thể chuyển sang App Server để điều khiển phiên, model picker và approval có cấu trúc. [Codex App Server](https://learn.chatgpt.com/docs/app-server)

## Claude và Gemini trong Antigravity

Antigravity **có CLI headless chính thức**. Native command hỗ trợ chọn model và JSONL; dùng cached login của CLI. Không được coi việc cài desktop là bằng chứng headless đã đăng nhập. [Headless mode](https://antigravity.google/docs/cli/headless/)

```text
agy models
agy -p <prompt> --model <selected-slug> --output-format stream-json
```

Kết quả `agy models` thực tế trên máy:

- `claude-sonnet-4-6`
- `claude-opus-4-6-thinking`
- `gemini-3.1-pro-high`, `gemini-3.1-pro-low`
- `gemini-3.6-flash-{high,medium,low}`
- `gemini-3.7-flash-{high,medium,low}`
- `gemini-3.8-flash-{high,medium,low}`
- `gpt-oss-120b-medium`

Các ký hiệu `{high,medium,low}` rút gọn ba slug riêng. Catalog không xác minh inference, quota còn lại hay quyền tài khoản. Tài liệu chính thức phân biệt model theo loại gói; cần refresh catalog và kiểm tra khả dụng lúc chạy. [Antigravity models](https://antigravity.google/docs/models/)

**Điều kiện trước khi bật execution:** `agy --help` đã kiểm tra không có flag tắt toàn bộ tools hoặc truyền một permission profile riêng cho mỗi lần gọi. Tài liệu mô tả permission rules trong global settings; `--sandbox` liên quan terminal, không tự chứng minh mọi tool bị giới hạn bởi task directory. Cần xác minh profile/isolation trước khi scheduler dùng CLI này. Đây là hạng mục nghiên cứu trong plan, không phải kết luận Antigravity thiếu khả năng tự động hóa. [Antigravity permissions](https://antigravity.google/docs/permissions/)

Không tự sửa global permission settings hoặc tái sử dụng OAuth token của Antigravity trong API khác. Bước triển khai tiếp theo: xác minh cấu hình per-run ở phiên bản mới hoặc worker chạy dưới OS user/VM riêng, sau đó thử cả thao tác được phép và thao tác vượt workspace trước khi bật scheduler.

SDK Python chính thức tồn tại, nhưng quickstart dùng Gemini API key; cấu hình Enterprise dùng Google Cloud. Chưa có bằng chứng SDK này cho phép đổi account Antigravity thành quyền API Claude. [Antigravity SDK](https://antigravity.google/docs/sdk/overview/)

## OpenCode và Z.AI

**OpenCode là integration chính trong thiết kế**, cùng cấp Codex và Antigravity; không chỉ là một connector phụ cho Z.AI. Nó phù hợp làm execution host cho nhiều provider do có session, chọn agent/model, quyền thực thi và stream sự kiện.

Local OpenCode v1 hỗ trợ `run --format json`, `--model`, `--dir`, `--session` và `--attach`; đã kiểm tra bằng help. Tài liệu v2 có thay đổi server/standalone, nên adapter cần ghim phiên bản và kiểm tra capability thay vì giả định hai phiên bản giống nhau. [OpenCode CLI](https://opencode.ai/docs/cli/), [OpenCode v2 commands](https://opencode.ai/v2/docs/cli/commands/)

Server chính thức cung cấp HTTP/OpenAPI và có auth. Nếu tích hợp ở bước sau, bind localhost và không dùng một shared server có nhiều dự án/quyền không được kiểm soát. [OpenCode server](https://opencode.ai/docs/server/)

Luồng tích hợp dự kiến: đọc OpenAPI của phiên bản đã ghim; discovery provider; tạo session cho worker; gửi prompt bất đồng bộ; nhận sự kiện; đưa permission request vào hàng pending của lead; resume hoặc abort theo quyết định. Server công bố các endpoint cho những chức năng này. Không cần giả lập thao tác desktop. [OpenCode server API](https://opencode.ai/docs/server/)

Mỗi vai trò có agent config riêng: lead lập kế hoạch, reviewer đọc và kiểm tra, worker ghi trong worktree được giao, skill architect nghiên cứu gói rồi đề xuất. Quyền agent và lựa chọn tools phải được thực thi ở host, không chỉ bằng prompt. [OpenCode agents](https://opencode.ai/docs/agents/), [OpenCode permissions](https://opencode.ai/docs/permissions/)

Bản nháp hiện mới discovery OpenCode; điều này phản ánh thứ tự viết nháp trước khi dừng triển khai, không phải mức ưu tiên sản phẩm. Bản kế hoạch cần một acceptance test riêng cho OpenCode: chạy/resume/abort, task chờ quyền không chặn task khác, giới hạn workspace, không nhầm key giữa tài khoản và không vô tình bật chia sẻ công khai.

Z.AI công bố endpoint Chat Completions dưới base URL `https://api.z.ai/api/paas/v4`. Chọn `openai_compatible`, nhập base URL này và API key ở khu vực credentials. Chọn model ID theo tài khoản thực tế; không tự điền giá hay benchmark. [Z.AI quickstart](https://docs.z.ai/guides/overview/quick-start)

Connector OpenCode của Z.AI phân biệt provider `Z.AI` và `Z.AI Coding Plan`. Không tự xem một gói là API dùng chung. [Z.AI với OpenCode](https://docs.z.ai/devpack/tool/opencode)

## API độc lập và credentials

Khu vực **Connections & Environments** dự kiến có hai luồng song song:

1. **Account/client:** nhận diện client, hướng dẫn hoặc mở login flow chính thức, giữ tham chiếu account/profile; không nhập password của tài khoản vào ứng dụng điều phối.
2. **API key:** nhập key bằng ô che nội dung, chọn provider/base URL/model, chọn môi trường `dev`, `test` hoặc `prod`, thử kết nối bằng thao tác rõ ràng, gán credential reference cho role. Test inference có thể tiêu quota và chỉ thực hiện khi người dùng chọn chạy.

Mỗi environment lưu metadata không bí mật: provider, endpoint, project scope, model allowlist, concurrency, hạn mức chi tiêu do người dùng đặt và nguồn quota. Key thuộc secret store; rule và prompt chỉ chứa `credential_ref`. Bản kế hoạch cần phân biệt ba trạng thái “đã nhập key”, “auth thành công” và “model inference thành công”. Một task lỗi key chuyển pending trên đúng connection, những task dùng connection khác tiếp tục chạy.

Chuyển từ `dev`/`test` sang `prod` là lựa chọn environment rõ ràng, không tự fallback sang key production khi development hết quota. Có thao tác thay key, thu hồi kết nối và xóa secret reference; audit chỉ lưu ID cùng thời điểm, không lưu key. Tài khoản client/subscription và API billing có resource pool riêng; một catalog model giống nhau không có nghĩa cùng entitlement hoặc cùng số dư.

- OpenAI native: dùng Responses API và adapter schema riêng cho request, output, usage và trạng thái; kiểm tra support theo model trước khi chọn. [OpenAI API overview](https://developers.openai.com/api/reference/overview)
- `anthropic`: base URL mặc định `https://api.anthropic.com/v1`, Messages API, header `x-api-key`. [Claude Messages](https://platform.claude.com/docs/en/api/messages/create)
- `gemini`: base URL mặc định `https://generativelanguage.googleapis.com/v1beta`, `generateContent`, header `x-goog-api-key`. [Gemini API](https://ai.google.dev/api/generate-content)
- `openai_compatible`: Chat Completions; mức tương thích tùy provider/model. Không phải mọi model OpenAI đều nhận cùng tham số hoặc có sẵn qua interface này.

Các API này không cấp tool thực thi trên máy trong adapter v0.1. Host phải kiểm tra và giới hạn file patch được model trả về. Key chỉ tồn tại trong bộ nhớ của tiến trình server; không nhúng vào prompt, URL, DB, log hay command line. Thiết kế nâng cấp lưu lâu dài nên dùng credential store của hệ điều hành, không dùng plaintext JSON trong repo.

HTTP chỉ được dùng với localhost; endpoint từ xa phải là HTTPS. Adapter từ chối redirect để không chuyển credential sang đích mới. Lỗi HTTP/CLI trả thông báo chung, không xuất nội dung lỗi có thể chứa key. Mỗi kết nối cần nhãn tài khoản và nguồn quota riêng để lead không tính nhầm ngân sách.

## Ghi chú nội bộ về bản nháp trước khi chuyển sang plan-only

Chạy:

```text
python -m unittest test_adapters -v
```

Trước chỉ dẫn dừng triển khai, đã chạy 5 test case trong `test_adapters.py`: chặn redirect và giấu upstream error body; validation endpoint/model; parse Codex success/usage; timeout/hủy subprocess; parse ba dạng API bằng dữ liệu giả. Các test đó pass, discovery CLI thực chạy thành công. **Chưa gọi inference thực bằng key hoặc account; chưa chứng minh workflow điều phối nhiều agent hoạt động.** Không chạy thêm test hoặc lệnh triển khai sau khi nhận chỉ dẫn plan-only.

CLI timeout 180 giây; hủy/timeout cố dừng process tree trên Windows. HTTP timeout socket 60 giây; hủy không thu hồi request đang chạy ở provider, chỉ bỏ kết quả khi phản hồi quay về. Không hoàn tiền token đã dùng. CLI chưa có hard output-token limit trong adapter: `max_output_tokens` chỉ được truyền cho HTTP API. Số token hiển thị lấy từ provider nếu có, nếu thiếu để `unknown`; chưa suy ra tiền từ subscription quota.

Một catalog tốt cần tách `discovered`, `selected`, `authenticated`, `inference_verified`; chỉ trạng thái cuối mới chứng minh task cụ thể đã chạy được. Nguồn benchmark cần kèm URL, ngày đo, loại bài test, phiên bản model, harness và cấu hình. Không dùng một điểm xếp hạng làm “năng lực tuyệt đối”, không trộn chi phí API với quota thuê bao.
