# Prompt dành cho Codex/lead/reviewer độc lập

Không giao prompt này cho task author để tự tạo ACCEPT. Reviewer dùng actual source và logs, không dựa văn phong chắc chắn.

```text
Review task <Gxx> revision <actual revision> tại D:\Hierarchical-Multi-Agent.
Bạn KHÔNG phải tác giả task đó. Nếu không độc lập, dừng và trả yêu cầu reviewer khác.

Đọc:
- AGENTS.md; docs/research/BRIEF.md; GEMINI_RULES.md
- docs/research/tasks/<actual definition>.md
- docs/research/tasks.json, result.schema.json, review.schema.json
- REVIEW_CHECKLIST.md
- reports/Gxx.md, results/Gxx.json và sidecars task cho phép
- exact dependency reviews và source-lock/locators được tham chiếu.

Chỉ research review; không install/login/inference/start server/run remote code/sửa app.
Kiểm tra schema/references/dependency revision/hash/allowed outputs.
Mở lại mọi critical claim và flags/routes/schema/permission/license used for decision;
sample >=3 noncritical claims nếu có, ghi IDs đã verify và phạm vi sampling.
CODE_TRACED cần actual pinned implementation caller/callee.
Không upgrade documentation thành runtime proof.
Giữ UNKNOWN/conflicts và reject unsupported certainty/scope drift.
Kiểm criterion Gxx-Axx riêng; selfcheck không thay evidence.

Chỉ viết docs/research/reviews/Gxx.json hợp review schema.
Tính hash actual result bytes nếu công cụ có; không tự tạo hash.
Decision: ACCEPT / ACCEPT_WITH_UNKNOWNS / REVISE / WAITING_INPUT.
Ghi allowed_downstream_assumptions và critical_unknowns.
Acceptance research không cho phép runtime inference/implementation/deploy.
Không sửa findings thay worker. Giao corrections nhỏ theo claim/criterion.
Final: decision, critical issues/unknowns, correction instructions, output path.
```

## Lead sau review

Chỉ lead cập nhật task manifest nếu muốn dùng nó làm bảng trạng thái. Những file này chưa có engine chạy tự động.
Nếu REVISE: giao lại cùng task/revision+1, chỉ corrections. Nếu dependencies thay đổi: review downstream affected claims lần nữa; acceptance hash cũ không theo output mới.
Nếu ACCEPT_WITH_UNKNOWNS: paste limitations vào brief task downstream; không chỉ gửi chữ ACCEPT.
G08, G16, G23 và G25 là các điểm đối chiếu tổng hợp; reviewer cần xem interface/claim conflicts liên task.

