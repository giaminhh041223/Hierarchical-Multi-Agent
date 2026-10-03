# Checklist review độc lập

Reviewer phải khác task author. Review nghiên cứu bằng evidence, không “Gemini nói đã verify”. Không tự chạy inference/install/test ngoài scope để bù lỗ hổng.

## Kiểm tra cấu trúc trước

- Đúng task ID/revision và chỉ outputs cho phép. Không sửa ứng dụng/settings/task/schema/reviews bằng worker.
- Dependencies có acceptance gắn đúng revision/hash; critical unknown được carry forward.
- JSON parse và result schema valid nếu có validator sẵn; chưa có thì manual structural review + ghi limitation, không install.
- IDs claim thuộc task, không trùng; IDs RQ/source tồn tại; acceptance đúng manifest; output paths nằm root/allowlist.
- Report và JSON nhất quán; sidecars có PROPOSED/SYNTHETIC/SOURCE_SNAPSHOT đúng loại.
- Commands executed=true có log/time/exit thực. Future tests vẫn NOT_RUN.
- Self-check coverage không được dùng làm reviewer decision.

## Kiểm tra claim

Reviewer mở lại **mọi critical claim**, mọi flag/route/schema/model/score/price/hash/license/permission được dùng để chọn nền, và tối thiểu 3 noncritical claims (hoặc tất cả nếu ít hơn). Ghi IDs đã verify; không gọi audit toàn bộ nếu chỉ sampling.
- DOCUMENTED: primary source đã mở, đúng section/date/version, không vượt doc scope.
- CODE_TRACED: full pinned revision, file/symbol/line locators tồn tại, caller/callee đã đọc; tests đọc không runtime.
- TEST_DEFINED: đúng test at revision, không “pass”.
- OBSERVED: tool allowed; original log/exit/time support statement; không secret.
- INFERRED: refs đủ, assumptions rõ, không sole proof cho critical capability.
- PROPOSED: không nhập lẫn vendor fact; claims source giả không cần tạo.
- UNKNOWN: impact, blocks_decision và bounded next verification.
- Search không thấy: inspected scope/terms; không proof absence.
- Khác version/edition/platform là conflicts/limitations, không chọn câu thuận ý.

## Kiểm tra semantics cần chặn

- Installed/catalog/auth/inference/quota riêng.
- Worktree/CWD/prompt không OS sandbox; path permission enforce hay weak mode rõ.
- Exit0/model finished không acceptance; soft denial không success tự động.
- Pending human request correlation/version/authority; elapsed wait không approval; independent task vẫn tiến.
- SQLite local atomicity không external exactly-once; crash/late result/cancel race có xử lý.
- Một task-state owner; retry gateway/adapter/scheduler không nhân call vô ý.
- Secret references không secrets; no raw env/auth store/log leakage.
- Cumulative usage != turn usage; estimated != billed; unknown price !=0; cancel != refund.
- Cloud docs không chứng minh selfhost edition; subscription không API entitlement.
- Knowledge/benchmark/skills không auto-authorize tool install hoặc execution.
- No made-up performance/safety/production-ready promises.

## Quyết định

**ACCEPT:** scope đầy đủ, acceptance đạt; critical claims được verify trong đúng evidence scope. Không có critical unknown dùng sai.

**ACCEPT_WITH_UNKNOWNS:** research scope đủ, unknowns explicit, không bịa. List limitations và allowed_downstream_assumptions; còn critical runtime gap thì không dùng kết quả để deploy hoặc declare capability true. Task downstream liên quan gap phải conditional hoặc chờ followup.

**REVISE:** corrections bounded theo criterion/claim, không giao feature mới. Tối đa hai vòng sửa task trước lead phân nhánh/thu nhỏ.

**WAITING_INPUT:** input/dependency/quyền/tools thật thiếu. Chỉ request dữ liệu cần, không lấy key khi documentation research không cần key.

Không ACCEPT khi evidence bịa, dependency stale, source revision chưa pin cho code claim hoặc scope vượt. Reviewer ghi decision vào `reviews/Gxx.json` hợp review.schema.json, sha256 của bytes actual result, reviewed_at và reviewer identity thật. Không forge hash/date/reviewer independence.
Lead có thể cập nhật tasks.json sau review; nếu chỉ là docs workflow thì không giả automatic scheduler đã enforce.

