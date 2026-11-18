# Judge audit

Chạy trong `src/`:
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10      # exit 0, PASS floors
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 30   # exit 1, FAIL floors
```
Coi judge như một bộ phân loại, lớp dương là FAIL (việc của judge là tìm lỗi). Verdict lấy từ CSV (replay), nhãn người làm chuẩn.

| Tiêu chí | n | κ | Precision | Recall | tp/fp/fn/tn | Tỉ lệ FAIL quan sát / sau hiệu chỉnh RG | Đạt FLOORS? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24/4/6/66 | 0.28 / 0.30 | Đạt | dùng, non-blocking |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9/0/21/70 | 0.09 / 0.30 | Không (κ và R dưới sàn) | loại khỏi gate |

FLOORS: κ >= 0.6, P >= 0.8, R >= 0.7. Specificity: tone 66/70 = 0.943, helpful 70/70 = 1.0.
Rogan-Gladen: p = (p_obs + spec - 1) / (sens + spec - 1). Với tone: (0.28 + 0.943 - 1) / (0.8 + 0.943 - 1) = 0.30, trùng với tỉ lệ FAIL theo nhãn người (30/100).

## Audit thủ công (10 ca bất đồng của tone, 5 ca của helpful)

| # | Case | Judge | Người | Ai đúng | Sửa rubric / nhãn |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha..." | PASS | FAIL | Người | Thêm vào rubric: xưng "em/anh", đuôi "nha/nhé" là suồng sã, FAIL. Xưng hô chuẩn là "LogiX - anh/chị". |
| 2 | tone H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ..." | PASS | FAIL | Người | Cùng quy tắc xưng hô; thêm ví dụ FAIL cho "bạn ơi". |
| 3 | tone H-029 "Dạ, vui lòng chờ... không cần nhắn thêm." | PASS | FAIL | Người | Judge chỉ nhìn "Dạ, vui lòng" ở đầu câu. Rubric ghi rõ: chấm cả câu, câu ra lệnh hay gạt khách là FAIL dù mở đầu lịch sự. |
| 4 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge trừ điểm vì "thiếu xin lỗi". Rubric ghi: xin lỗi không bắt buộc, ngắn mà đủ ý và lễ phép là PASS. |
| 5 | tone H-051 "Dạ, LogiX đã refund 90.000đ..." | FAIL | PASS | Người | Thêm danh sách từ CS LogiX cho phép dùng ("refund", "ship", "voucher"). |
| 6 | tone H-063 "...đã hoàn 20.000đ và sẽ hoàn thêm..." | PASS | FAIL | Người, nhưng không phải lỗi tone | Hứa hẹn ngoài kết quả hệ thống là lỗi nội dung/tiền. Chuyển sang grader code (FM-08), bỏ khỏi rubric tone để không lẫn hai tiêu chí. |
| 7 | tone H-070 "...cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Rubric: emoji cười trong ngữ cảnh khiếu nại là FAIL. |
| 8 | tone H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn..." | FAIL | PASS | Judge (nhãn người sai) | Note trong CSV ghi người chấm đọc nhầm ticket. Sửa nhãn H-081 thành FAIL, ghi lý do và người duyệt; tính lại κ/P/R (fp 4 thành 3, tp 24 thành 25). Các case từ chối hoàn tiền nên có 2 người chấm. |
| 9 | tone H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ..." | FAIL | PASS | Người | Lỗi gõ lặp không làm sai giọng. Rubric: lỗi chính tả nhỏ không đổi nghĩa thì không FAIL tone. |
| 10 | tone H-094 "Da, LogiX da hoan 40.000đ..." | PASS | FAIL | Người | Rubric: tiếng Việt mất dấu hoặc kiểu dịch máy là FAIL. Có thể kiểm bằng code (tỉ lệ ký tự có dấu). |
| 11 | helpful HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger 40.000đ) | PASS | FAIL | Người | Judge không được xem ledger nên không thể biết số sai. Sửa rubric không giải quyết được; phải chấm bằng code (`reply_amount_matches_ledger`). |
| 12 | helpful HL-016 reply dài, xin lỗi 2 lần, "đã hoàn 55.000đ" (ledger 35.000đ) | PASS | FAIL | Người | Judge ưu ái reply dài, xin lỗi nhiều: các reply FAIL bị bỏ sót dài trung bình 156 ký tự, các reply bị bắt chỉ 31 ký tự. Rubric: xin lỗi không được cộng điểm helpful. |
| 13 | helpful HL-043 xin lỗi dài, "đã hoàn 35.000đ cho đơn O-202" (ledger 20.000đ) | PASS | FAIL | Người | Giống hệt lỗi FM-08 của C-008 trong eval set. Thêm bằng chứng là judge không thay được grader code cho tiền. |
| 14 | helpful HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL (xưng hô) | Người | Đây là lỗi tone; để judge tone (đã calibrate) chấm, bỏ tiêu chí xưng hô khỏi rubric helpful. |
| 15 | helpful HL-019 "Đơn O-909 không được hoàn." | FAIL | FAIL (cụt) | Đồng ý | Cả 9 FAIL mà judge bắt được đều là reply ngắn (lạc đề, cụt, không hỏi mã đơn). Judge thực chất chỉ học "ngắn = không helpful". |

## Kết luận

- tone_ok: dùng được (κ 0.757, P 0.857, R 0.8 đều trên sàn). Để non-blocking và luôn báo kèm tỉ lệ đã hiệu chỉnh (0.28 lên 0.30), vì judge vẫn bỏ sót 6/30 FAIL (chủ yếu xưng hô suồng sã) và báo nhầm 4/70. Áp dụng các sửa rubric ở trên, sửa nhãn H-081, rồi calibrate lại.
- helpful: loại khỏi gate. Ma trận 9/0/21/70 cho precision 1.0 nhưng recall chỉ 0.3: judge bỏ sót 21/30 FAIL, trong đó có cả 18 ca sai tiền (judge không thấy ledger) và 3 ca xưng hô. Nếu dùng làm gate thì đúng loại lỗi đắt nhất (FM-08, báo sai số tiền) sẽ lọt qua. κ 0.375 < 0.6 cũng cho thấy đồng thuận yếu.
- Rogan-Gladen của helpful ra 0.30, nhưng con số này dựa trên sensitivity 0.3 ước lượng từ chỉ 30 FAIL nên sai số rất lớn. Hiệu chỉnh không biến một judge kém thành judge dùng được.
- Thay thế: tiền và approval chấm bằng code (`refund_amount_correct`, `approval_bypass`, metric FM-08). Phần "helpful" còn lại (hỏi mã đơn khi thiếu, không lạc đề) có thể chấm bằng code theo status (`needs_info` thì phải hỏi mã đơn), hoặc viết lại rubric rồi calibrate lại.
- Rủi ro còn lại: judge mới được kiểm trên dữ liệu replay đã công khai (100 dòng mỗi tiêu chí). Cần nhãn người mới làm tập held-out, và sau khi sửa rubric phải đo lại trên tập chưa thấy.
