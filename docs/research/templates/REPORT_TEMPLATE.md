# Gxx — <task title>

> TEMPLATE, chưa có findings. Thay Gxx bằng task đang được giao; không copy placeholders thành fact.

- Revision:
- Task status: PENDING_REVIEW / PARTIAL / WAITING_INPUT
- Scope và RQ IDs:
- Inputs đã đọc, dependency review revision/hash:
- Snapshot/version/platform inspected:
- Sources/code files inspected; không claim đã đọc phần chưa mở:
- Runtime tests: NOT_RUN
- Schema validated: true/false; tool và errors nếu có.

## 1. Kết quả chính
Tối đa 5 findings. Mỗi finding dẫn claim ID. Không gọi recommendation là observation.

## 2. Bằng chứng
| Claim ID | Statement | Evidence level | Version/platform scope | Locator | Limitations |
|---|---|---|---|---|---|
| Gxx-C01 | <replace> | <one enum> | <replace> | <source/commit/file/symbol/lines/section> | <replace> |

Mỗi claim chỉ dùng một evidence level. Nếu doc và code xác minh một statement, tạo claims riêng cho mỗi nguồn hoặc ghi code là claim chính và doc bổ trợ. INFERRED cần derived_from và giả định; PROPOSED không có vendor capability claim. UNKNOWN cần câu hỏi/cách verify.
Locators trong JSON là chi tiết canonical. Link code permalink chỉ khi đã mở/pin thực; không bịa filename hoặc lines. Không trích quá 25 từ mỗi web source.

## 3. Analysis theo từng bước task
Ghi step number → kết quả/claim IDs hoặc blocker. Dùng table/flow nếu task cần. Mọi diagram/capability cell có claim refs; diagram thiết kế mang PROPOSED.
Không thêm implementation dù phát hiện cách sửa.

## 4. Unknowns và conflicts
| ID | Question/conflicting claims | Impact | Blocks decision? | Next verification |
|---|---|---|---|---|

UNKNOWN không phải NO. “Not found” kèm inspected scope/search terms. Giữ fetch/version/platform limitations.

## 5. Future experiment / proposal
TEST_PLAN/PROPOSED, chưa thực hiện. Setup, stimulus, observable result, necessary authorization, cleanup/rollback và điểm dừng. Không giả định key/login/inference được authorize.

## 6. Acceptance self-check
| Criterion ID của task | Covered? | Claim/section/output refs | Gap |
|---|---|---|---|

Đây là tự kiểm tra coverage, không reviewer acceptance. Coverage true không chứng minh runtime test pass.

## 7. Hoạt động và đầu ra
Files thực đã ghi, commands thực chạy có redaction/timestamp/exit code/log ref. Command đề xuất phải executed=false; không copy terminal giả.
Schema validation chỉ true nếu actual validator đã chạy. Nếu môi trường không có validator, không install; báo false và chuyển reviewer.
Final task status, unresolved scope và đề xuất followup hẹp. Dừng sau task này.

