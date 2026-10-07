# Bộ việc chuẩn cho `orctram bench`

Năm việc, từ nhỏ đến lớn, để trả lời bằng số liệu: **cả đội có hơn một agent làm một mình không, và ở cỡ việc nào?**

| Việc | Cỡ | Cả đội có lợi thế gì |
|---|---|---|
| `01-small-slugify` | một hàm | Không có: đây là mốc kiểm tra chi phí điều phối. |
| `02-parallel-modules` | bốn module độc lập | Chạy song song, mỗi worker một module. |
| `03-refactor-invoice` | tách một file thành ba module, kèm sửa một lỗi | Plan và review có thể bắt lỗi thiết kế. |
| `04-spec-traps` | một module, năm quy tắc viết chính xác nhưng dễ đọc sai (làm tròn half-up, "ít nhất", "mỗi kg bắt đầu", xu dư cho phần đầu …), 5 check | Examiner: test viết từ mục tiêu có bắt được chỗ đọc sai không. |
| `05-wide-parallel` | sáu module độc lập, mỗi module là việc thật (semver, ini, LRU, Luhn, khoảng, cron), 6 check | Chạy song song: chỗ duy nhất đội có thể nhanh hơn một agent. |

Mỗi việc có:
- `seed/`: repo khởi đầu;
- `goal.md`: mục tiêu đưa cho agent;
- `checks/`: check ẩn. File nằm ngoài repo của agent, nên không agent nào thấy; `bench` chạy chúng từ gốc của kết quả;
- `solution/`: lời giải mẫu. Test `benchmark_tasks_are_sound` kiểm tra check ẩn trượt trên `seed/` và qua với `seed/` cộng `solution/`.

## Chạy

Chạy trên máy của bạn: agent thật tốn quota, đừng chạy trong CI.

```bash
python benchmarks/run_suite.py --team my-team.json --repeat 3 --mode auto --mode solo --engine-solo --examiner
```

- `--team`: team cho nhánh "cả đội", cùng dạng `.orch/team.json`.
- `--solo agent/model`: agent làm một mình. Mặc định là lead của team. Để so công bằng, dùng cùng model với lead.
- `--mode auto` / `--mode solo`: thêm nhánh "cả đội ở chế độ đó".
- `--engine-solo`: thêm nhánh chế độ `solo` với chính agent/model của nhánh solo làm worker duy nhất. So nó với nhánh solo để biết vòng verify và thử lại của engine đáng bao nhiêu khi không đổi model. Cần `"verify"` trong file team.
- `--examiner`: thêm nhánh engine solo có examiner (reviewer của team viết test chấp nhận từ mục tiêu trước khi worker làm). Cần `"verify"`.
- `--tasks 02 03`: chỉ chạy vài việc.
- `--pool <thư mục suite> …`: không chạy agent, chỉ gộp kết quả của các đợt trước (cùng team, cùng tên nhánh) thành một bảng.

Mỗi việc được chép vào một repo git mới ở `~/.orchestra/bench-suite/<thời điểm>/<việc>/`. Bản tổng hợp nằm ở `summary.md` cùng thư mục.

## Đọc kết quả

- **Runs passing every check:** số lần đạt hết check ẩn. Đây là chất lượng.
- **$:** chi phí CLI báo, hoặc ước tính theo giá OpenRouter (dấu `~`). Model free tính 0.
- **Agent calls, questions:** chi phí điều phối và số lần phải hỏi bạn.
- **Stopped because:** vì sao một lần chạy không xong (câu hỏi đang chờ, task thất bại, lỗi của agent). Chấm trượt vì run dừng khác với chấm trượt vì code sai.
- Một lần chạy không đủ để kết luận; dùng `--repeat 3` trở lên.
- **Pooled:** cuối `summary.md` có bảng gộp theo việc và nhánh, kèm khoảng tin cậy 95% (Wilson). Hai nhánh có khoảng chồng nhau là chưa phân biệt được: 3/3 cho khoảng 44–100%, 2/3 cho 21–94%.
