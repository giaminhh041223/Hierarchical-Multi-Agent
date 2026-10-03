# Kế hoạch UI/UX cho web UI

Mục tiêu: web UI trông chuyên nghiệp và dễ đọc, nhưng giữ nguyên mô hình bảo mật ở [PLAN.md §13](../PLAN.md).

## 1. Đề bài

- **Chủ thể:** bảng điều khiển một "dàn nhạc" agent lập trình chạy trên máy của bạn.
- **Người dùng:** một lập trình viên. UI mở cạnh editor; phần lớn thời gian bạn chỉ liếc vài giây rồi quay lại việc khác.
- **Việc chính, theo tần suất:**
  1. Biết có gì đang chờ mình: duyệt plan, trả lời câu hỏi, lỗi đăng nhập, chạm ngân sách.
  2. Duyệt hoặc sửa plan.
  3. Xem tiến độ: task nào đang chạy, ai làm, kẹt ở đâu, tốn bao nhiêu token.
  4. Gỡ kẹt: thử lại, giao lại, huỷ.
  5. Thiết lập, ít khi dùng: agent, đăng nhập, vault, team, model, skill.

## 2. Hiện trạng

Đọc từ [orch/ui.html](../orch/ui.html):

| Vấn đề | Hậu quả |
|---|---|
| Mọi chữ cùng cỡ, cùng độ đậm | Mắt không biết nhìn đâu trước. |
| Trạng thái chỉ phân biệt bằng màu chữ | Người mù màu đỏ–xanh không phân biệt được `done` và `failed` (WCAG 1.4.1). |
| Cứ 3 giây dựng lại cả tab | Mất vùng chữ đang chọn, nên khó copy từ log; khung log cuộn về đầu. |
| Ô nhập dùng placeholder thay nhãn | Nhãn biến mất khi bắt đầu gõ. |
| Kết quả thao tác là một dòng chữ nhỏ trên header | Dễ bỏ lỡ; trình đọc màn hình không đọc (không có `aria-live`). |
| Plan, Report, Console là các khối `pre` dài nối nhau | Bảng task bị đẩy xuống xa. |
| Tab xếp theo thứ tự làm ra, không theo tần suất | Vận hành và thiết lập lẫn vào nhau. |
| Sơ đồ DAG: đầu node viết `T1 · running`, màu chỉ ở viền mảnh, không thu phóng | Khó đọc khi plan lớn. |
| Tab Team là một ô JSON | Phải nhớ cấu trúc `team.json`. |
| Chỉ có tiếng Anh | Tài liệu và cách bạn làm việc là tiếng Việt. |

## 3. Ràng buộc (không đổi)

- Một file `ui.html`: không bước build, không framework, không thư viện ngoài.
- CSP có nonce:
  - không thuộc tính `style` inline; dùng class, hoặc gán qua CSSOM (`el.style.x = …`);
  - không dùng HTML thô; mọi dữ liệu là text node (test `ui_server_security` kiểm tra);
- Không tải gì từ ngoài: không font web, không CDN, không ảnh. Biểu tượng là ký tự Unicode hoặc SVG dựng bằng DOM. Muốn dùng font web thì phải nới CSP (`font-src`): đó là quyết định bảo mật của bạn.
- Server chỉ dùng thư viện chuẩn. Endpoint mới đi qua cùng kiểm tra token, Host, Origin.
- `ui.html` giữ dưới khoảng 60 KB.

## 4. Hướng thiết kế

Một câu: **bảng điều khiển yên tĩnh, đọc nhanh; màu chỉ dùng để báo trạng thái, nên chỗ nào có màu là chỗ có chuyện.**

1. **Màu là trạng thái.** Nút, link, viền dùng mực trung tính; nút chính là nền mực, chữ màu giấy. Nhờ vậy màu hổ phách "cần bạn" luôn nổi nhất trang.
2. **Không chỉ dựa vào màu.** Mỗi trạng thái có ký hiệu và chữ đi kèm.
3. **Việc cần bạn luôn ở trên cùng**, và số việc đó hiện trên header ở mọi tab.
4. **Dày thông tin nhưng có thứ bậc.** Một cỡ chữ cơ bản; tiêu đề phân biệt bằng cỡ và độ đậm, không viết hoa toàn bộ.
5. **Một điểm nhấn duy nhất: tổng phổ (score) của run** (§9).
   - Mỗi agent là một dòng kẻ như một bè nhạc; mỗi lần thử là một nốt kéo dài theo thời gian.
   - Nó gắn với cái tên Orchestra, và trả lời được câu hỏi "ai đang làm gì, ai rảnh, ai vừa hết usage".
   - Mọi thứ khác giữ im lặng.

Đã soát với danh sách "dấu hiệu template" của skill frontend-design:
- Không dùng: nền kem với serif và màu đất nung; nền đen với một màu neon; bộ thẻ SaaS bo góc đồng loạt có bóng mờ; nhãn chữ hoa giãn cách; chuỗi meta nối bằng dấu chấm giữa (sẽ sửa `T1 · running` trong DAG); `→` gắn sau chữ trên nút.
- Monospace chỉ cho thứ thật sự là mã: ID task, lệnh verify, log, đường dẫn. Nhãn nhỏ dùng font giao diện.

## 5. Token

### Màu

Tỉ lệ tương phản tính theo công thức WCAG 2.x, trên nền trang và trên bề mặt (sáng / tối).

| Tên | Sáng | Tối | Dùng cho | Tương phản |
|---|---|---|---|---|
| `paper` | `#F3F4F1` | `#16191C` | Nền trang | |
| `surface` | `#FFFFFF` | `#1E2226` | Panel, bảng, ô nhập | |
| `ink` | `#1C2024` | `#E4E6E3` | Chữ chính, nút chính, vòng focus | 14,8–16,4 / 12,8–14,1 |
| `muted` | `#545B63` | `#A0A8B0` | Chữ phụ | 6,2–6,9 / 6,7–7,3 |
| `line` | `#DADDD8` | `#2A2F34` | Đường kẻ trang trí (không cần tương phản) | |
| `control` | `#7E858C` | `#69717A` | Viền ô nhập và nút phụ (cần ≥ 3:1) | 3,4–3,7 / 3,2–3,6 |
| `running` | `#1F5FBF` | `#7DAAF0` | Đang chạy, đang kiểm, đang tích hợp | 5,5–6,1 / 6,8–7,5 |
| `done` | `#1D7443` | `#5CC489` | Xong | 5,2–5,8 / 7,4–8,2 |
| `waiting` | `#8F5300` | `#F0AE4C` | Cần bạn, chờ lead | 5,6–6,2 / 8,3–9,1 |
| `failed` | `#B3261E` | `#FF8A80` | Lỗi, đã huỷ | 5,9–6,5 / 7,0–7,7 |

- Nền nhạt của trạng thái (ví dụ thẻ "Chờ bạn") pha bằng `color-mix(in srgb, var(--waiting) 10%, var(--surface))`.
- Theme theo hệ điều hành (`prefers-color-scheme`). Nút chuyển tay là tuỳ chọn ở Pha 3.

### Chữ

- **Giao diện:** `"Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, "Noto Sans", sans-serif`.
  - Segoe UI Variable có sẵn trên Windows 11, đủ dấu tiếng Việt, có trục optical size.
  - Tiêu đề dùng `"Segoe UI Variable Display"`.
- **Mã:** `"Cascadia Mono", Consolas, ui-monospace, "SF Mono", Menlo, monospace`.
- **Thang cỡ (px):** 12 chú thích, 13 bảng dày, 14 cơ bản, 16 tiêu đề mục, 20 tiêu đề trang (mục tiêu của run).
- Line-height 1,45 cho thân, 1,25 cho tiêu đề. Chỉ dùng độ đậm 400 và 600.
- Số dùng `font-variant-numeric: tabular-nums`, để cột thời gian và token thẳng hàng.
- Đoạn văn (mô tả, câu hỏi, plan) giới hạn `max-width: 75ch`.

### Khoảng cách, bo góc, bóng

- Lưới 4px: 4, 8, 12, 16, 24, 32.
- Bo góc theo thứ bậc: 4px cho nút, ô nhập, badge; 8px cho panel lớn; node DAG 6px.
- Không đổ bóng, trừ toast và menu nổi (dùng chung một bóng).

## 6. Bố cục

Tab Run trên desktop (rộng ≥ 1100px):

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Orchestra   calc / run 20261003-021406   ● engine đang chạy    [! Cần bạn 2] │
│ Run   Sự kiện   Tri thức          Agent   Team   Vault   Model   Skill       │
├──────────────────────────────────────────────────────────────────────────────┤
│ Thêm máy tính dòng lệnh có test                                 [Huỷ tất cả] │
│ ▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒▒░░░░░░   5 xong, 2 đang chạy, 1 chờ bạn     41k / 200k token │
├─────────────────────────────┬────────────────────────────────────────────────┤
│ Chờ bạn (2)                 │ Sơ đồ task                     [−] [+] [Vừa]   │
│ ┃ PLAN  Plan v2 sẵn sàng    │                                                │
│ ┃ [Duyệt] [Sửa sơ đồ]       │   DAG; khi sửa plan thì kéo để nối phụ thuộc   │
│ ┃ T3  codex lỗi đăng nhập   │                                                │
│ ┃ [Thử lại] [Giao lại ▾]    │                                                │
├─────────────────────────────┴────────────────────────────────────────────────┤
│ Tổng phổ   codex/gpt-5    ━━ T1 ━━━   ━ T3 ✕                                 │
│            agy/gemini           ━━━━━ T2 ━━━━━━━                             │
├──────────────────────────────────────────────────────────────────────────────┤
│ Bảng task (tiêu đề cột dính khi cuộn)                                        │
│ ▸ Plan    ▸ Báo cáo    ▸ Console engine                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Căn trái mọi thứ; số căn phải trong bảng.
- Rộng dưới 1100px: cột "Chờ bạn" nằm trên sơ đồ. Dưới 640px: bảng cuộn ngang trong khung riêng, thanh tab cuộn ngang.
- Tab chia hai nhóm cách nhau bằng khoảng trống: vận hành (Run, Sự kiện, Tri thức) và thiết lập (Agent, Team, Vault, Model, Skill).
- Bấm vào "Cần bạn" trên header thì về tab Run, cuộn tới thẻ đầu tiên.

## 7. Thành phần

**Badge trạng thái:** ký hiệu, chữ và màu đi cùng nhau.

| Trạng thái | Ký hiệu | Nhãn |
|---|---|---|
| `todo` | ○ | chờ |
| `running`, `verifying`, `integrating` | ▶ | đang chạy / đang kiểm / đang tích hợp |
| `done` | ✓ | xong |
| `pending_user` | ! | cần bạn |
| `needs_lead` | ? | chờ lead |
| `failed` | ✕ | lỗi |
| `cancelled` | – | đã huỷ |

- Badge đang chạy có nhịp nhẹ; tắt khi `prefers-reduced-motion`.
- Tooltip giữ tên gốc (`pending_user`) để khớp với log và CLI.

**Thẻ "Chờ bạn":**
- Viền trái 4px màu `waiting`; câu hỏi tối đa 75ch.
- Nút trả lời nhanh theo loại câu hỏi:
  - PLAN: Duyệt, Sửa sơ đồ;
  - lỗi đăng nhập: Thử lại, Giao lại;
  - BUDGET: Tiếp tục, Dừng.
- Ô trả lời tự do có nhãn.

**Nút:**
- Chính: nền `ink`, mỗi khu vực tối đa một nút.
- Phụ: viền `control`.
- Nguy hiểm: chữ `failed`; luôn hỏi xác nhận và nói rõ hậu quả.
- Cao tối thiểu 32px; vùng bấm ít nhất 24×24px (WCAG 2.5.8).

**Ô nhập:** nhãn luôn hiện phía trên; placeholder chỉ là ví dụ.

**Bảng:**
- Tiêu đề cột dính; hàng đổi nền khi rê chuột.
- Cột ID và lệnh dùng font mã.
- Chữ dài cắt bằng dấu ba chấm, tooltip hiện đầy đủ.

**Toast:**
- Một vùng `role="status"` ở góc dưới phải; lỗi dùng `role="alert"`.
- Thông báo thường tự ẩn sau 5 giây; lỗi giữ tới khi bạn đóng.
- Lời nhắn dùng đúng động từ của nút: nút "Gửi câu trả lời" cho ra "Đã gửi câu trả lời".

**Khối dài** (Plan, Báo cáo, Console): dùng `<details>` có sẵn của HTML, nhớ trạng thái mở qua các lần làm mới.

**Trạng thái trống:** một câu nói thứ gì đang thiếu, kèm nút làm việc đó. Ví dụ: "Chưa có team." [Chọn team].

**Panel chi tiết task** (bấm vào node hoặc hàng):
- spec: acceptance, scope, verify;
- các lần thử: agent, model, kết quả, token, thời gian;
- handoff;
- đường dẫn thư mục bằng chứng.

Cần thêm endpoint `GET /api/task?id=`.

## 8. Sơ đồ DAG và chế độ sửa plan

**Node:**
- Cỡ 200×56; viền trái màu trạng thái.
- ID bằng font mã, kèm badge; tiêu đề một dòng; tên worker.
- Node đang chọn có viền `ink` 2px.

**Cạnh:**
- Phụ thuộc khai báo: nét liền. Thứ tự ngầm (work chạy sau PLAN và SKILLS): nét đứt.
- Cạnh vào và ra node đang chọn được tô đậm.

**Điều hướng:**
- Nút −, +, Vừa khung; Ctrl + lăn chuột để thu phóng.
- Khung cuộn có sẵn của trình duyệt dùng để di chuyển.
- Thêm một lượt barycenter để giảm cạnh cắt nhau (giới hạn đã biết ở PLAN §16).

**Chế độ sửa plan:** đã có, đang dùng giao diện hiện tại.
- Kéo từ node A thả vào node B: B phụ thuộc A.
- Bấm vào cạnh để xoá.
- Chọn worker cho từng node.
- Dùng bàn phím thì sửa phụ thuộc bằng danh sách ô đánh dấu.
- Lưu hoặc Huỷ.

Pha 2 chỉ đổi giao diện, giữ nguyên hành vi và API.

**Khả năng tiếp cận:**
- SVG có `role="img"` và `aria-label` tóm tắt.
- Bảng task bên dưới là phương án thay thế đầy đủ.
- Node nhận focus bằng Tab; Enter mở panel chi tiết.

## 9. Tổng phổ: điểm nhấn của trang

- Trục ngang là thời gian từ đầu run; mỗi dòng là một agent/model, lấy từ bảng `attempts`.
- Mỗi lần thử là một thanh từ lúc bắt đầu đến lúc kết thúc (đang chạy thì kéo tới hiện tại), nhãn là ID task.
- Màu thanh: thành công dùng `done`, đang chạy dùng `running`, thất bại dùng `failed` kèm ✕. Tooltip ghi loại lỗi (quota, verify, scope …).
- Nhìn vào là thấy:
  - mức song song thật;
  - agent nào đang rảnh;
  - task nào bị xoay vòng do hết usage (thanh nhảy sang dòng khác).
- Dữ liệu: thêm `attempts` vào `/api/state`, chỉ các cột không nhạy cảm (task, kind, agent, model, started, ended, outcome, failure, token).

## 10. Khả năng tiếp cận: mức sàn, không bàn lại

- WCAG 2.2 AA: tương phản như bảng §5; không truyền tin chỉ bằng màu.
- Focus luôn thấy rõ: `:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px }`.
- Mọi thao tác dùng được bằng bàn phím; thứ tự Tab theo thứ tự đọc.
- Tab đang mở có `aria-current="page"`.
- `prefers-reduced-motion`: tắt nhịp và chuyển động.
- Thu phóng 200% không mất nội dung; rộng 360px vẫn dùng được.
- Thuộc tính `lang` của trang khớp ngôn ngữ đang hiển thị.

## 11. Ngôn ngữ và lời văn

- Giao diện tiếng Việt mặc định, có nút chuyển sang tiếng Anh (lưu trong `localStorage`).
  - Một bảng từ điển trong `ui.html`; thiếu bản dịch thì hiện tiếng Anh.
  - Thuật ngữ kỹ thuật giữ nguyên: task, plan, worker, lead, reviewer, commit, token.
- Viết hoa đầu câu; nút là động từ nói rõ điều sẽ xảy ra.
- Thông báo lỗi không xin lỗi; nói chuyện gì đã xảy ra và cách sửa.

## 12. Lộ trình

Mỗi pha một commit; chạy đủ bộ test trên Windows và WSL.

| Pha | Nội dung | Xong khi |
|---|---|---|
| 0. Công cụ | Bạn chọn plugin/skill ở §13. | Đã cài, hoặc quyết định không cài. |
| 1. Nền tảng | <ul><li>Token màu, chữ, khoảng cách; sáng/tối.</li><li>Nút, ô nhập có nhãn, bảng có tiêu đề dính.</li><li>Badge có ký hiệu và chữ.</li><li>Toast có `aria-live`.</li><li>`<details>` cho khối dài.</li><li>Không dựng lại khi dữ liệu không đổi, để giữ vùng chọn và vị trí cuộn.</li><li>Test mới: trang không chứa `http://` hay `https://`, chặn CDN và font ngoài.</li></ul> | <ul><li>Bộ test pass.</li><li>Script tương phản pass.</li><li>Ảnh chụp sáng/tối ở 1280px và 375px không vỡ.</li></ul> |
| 2. Tab Run | <ul><li>Header run: thanh tiến độ, token.</li><li>"Chờ bạn" lên đầu, có nút trả lời nhanh.</li><li>DAG mới: thu phóng, barycenter, chọn node.</li><li>Panel chi tiết task (`/api/task`).</li><li>Tổng phổ (`attempts` trong `/api/state`).</li></ul> | <ul><li>Duyệt plan và gỡ kẹt được hoàn toàn bằng bàn phím.</li><li>Đã xem lại ảnh chụp.</li></ul> |
| 3. Tab thiết lập | <ul><li>Agent: danh sách có trạng thái đăng nhập và probe.</li><li>Team: form chọn lead, reviewer, worker từ danh sách model dùng được; JSON thành chế độ nâng cao.</li><li>Vault có nhãn; Model sắp xếp được.</li><li>Trạng thái trống có nút hành động.</li><li>Tiếng Việt/Anh.</li></ul> | Tạo team mới không cần gõ JSON. |
| 4. Soát và hoàn thiện | <ul><li>Audit bằng web-design-guidelines (bản ghim).</li><li>Đi hết các luồng chỉ bằng bàn phím; thử với Narrator.</li><li>Reduced motion, thu phóng 200%.</li><li>Cập nhật ảnh chụp trong README.</li></ul> | Audit không còn lỗi mức bắt buộc. |

## 13. Plugin và skill hỗ trợ

Đã tra cứu, chưa cài gì.
- Cài plugin là ghi vào cấu hình Claude Code toàn cục của bạn (`~/.claude`), nên cần bạn đồng ý.
- Lệnh `/plugin` chạy trong `claude` ở terminal.

| Tên | Nguồn | Dùng để | Lưu ý |
|---|---|---|---|
| **frontend-design** | Anthropic, `claude-plugins-official`; Apache 2.0; khoảng 41 KB | <ul><li>Chốt hướng thẩm mỹ và token.</li><li>Tự phê bình qua ảnh chụp.</li></ul> | <ul><li>Hay đẩy font riêng; ở đây CSP chặn font ngoài nên dùng font hệ thống (§5).</li><li>Đã có sẵn trong bản clone marketplace trên máy.</li><li>Cài: `/plugin install frontend-design@claude-plugins-official`.</li></ul> |
| **web-design-guidelines** | Vercel, `vercel-labs/agent-skills` | Soát UI theo hơn 100 quy tắc: accessibility, form, focus, chữ, hiệu năng. | <ul><li>Mỗi lần chạy, skill tải bộ quy tắc từ raw.githubusercontent.com; nên ghim một bản theo commit.</li><li>Cài: `npx skills add https://github.com/vercel-labs/agent-skills --skill web-design-guidelines`.</li></ul> |
| **playground** | Anthropic, `claude-plugins-official`; khoảng 61 KB | Dựng trang HTML một file để thử palette và thang chữ trước khi sửa `ui.html`. | <ul><li>Tuỳ chọn.</li><li>Cài: `/plugin install playground@claude-plugins-official`.</li></ul> |
| **ui-ux-pro-max** | `nextlevelbuilder/ui-ux-pro-max-skill`; MIT | Kho palette, cặp font, quy tắc UX; chạy offline bằng Python. | <ul><li>Lớn, chủ yếu nhắm tới landing page và SaaS. Token ở §5 đã đủ nên không cần.</li><li>Cài: `/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill`, rồi `/plugin install ui-ux-pro-max@ui-ux-pro-max-skill`.</li></ul> |

- **Không cần:** Playwright MCP, Chrome DevTools MCP. Trình duyệt tích hợp trong Claude app đã chụp ảnh, đọc console và cây accessibility.
- **Đề xuất:** cài frontend-design; dùng bản ghim của web-design-guidelines cho Pha 4; playground tuỳ chọn.

Nguồn:
- https://github.com/anthropics/claude-code/tree/main/plugins/frontend-design
- https://github.com/vercel-labs/agent-skills
- https://vercel.com/design/guidelines
- https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- https://github.com/wilwaldon/Claude-Code-Frontend-Design-Toolkit
- https://snyk.io/articles/top-claude-skills-ui-ux-engineers/

## 14. Quyết định cần bạn

1. Ngôn ngữ mặc định của UI: tiếng Việt (đề xuất) hay tiếng Anh.
2. Cài plugin nào ở §13.
3. Giữ CSP chặn font ngoài (đề xuất). Muốn font riêng thì phải nhúng file font và thêm `font-src`, tức là đổi chính sách bảo mật.
