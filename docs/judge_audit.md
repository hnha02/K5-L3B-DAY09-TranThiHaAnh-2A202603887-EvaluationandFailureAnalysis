# Judge audit

Chạy (từ `src/`):
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10      # exit 0, PASS floors
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 30   # exit 1, FAIL floors
```
Judge là bộ phân loại với **FAIL là lớp dương** (việc của judge là tìm lỗi). Backend: replay (verdict lưu sẵn trong CSV), nhãn người là chuẩn.

| Tiêu chí | n | κ | Precision | Recall | Ma trận (tp/fp/fn/tn) | Tỉ lệ FAIL quan sát → hiệu chỉnh (Rogan-Gladen) | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | 0.28 → 0.30 | **Đạt** | **dùng** (non-blocking, báo cáo kèm tỉ lệ hiệu chỉnh) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9 / 0 / 21 / 70 | 0.09 → 0.30 | **Không** (κ, R dưới sàn) | **loại** khỏi gate |

Specificity: tone 66/70 = 0.943; helpful 70/70 = 1.0.
Rogan-Gladen: p = (p_obs + spec − 1) / (sens + spec − 1). Với tone: (0.28 + 0.943 − 1)/(0.8 + 0.943 − 1) = 0.30, khớp tỉ lệ FAIL của người (30/100).

## Case audit thủ công (10 bất đồng của tone + 5 của helpful)

| # | Case | Judge nói | Người nói | Ai đúng? | Hành động sửa rubric / nhãn |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha…" | PASS | FAIL | Người | Rubric thêm: xưng "em/anh", hậu tố "nha/nhé" = suồng sã → FAIL; xưng hô chuẩn là "LogiX – anh/chị". |
| 2 | tone H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ…" | PASS | FAIL | Người | Cùng quy tắc xưng hô: "bạn" không dùng với khách; thêm 2 ví dụ few-shot FAIL cho "bạn ơi". |
| 3 | tone H-029 "Dạ, vui lòng chờ… không cần nhắn thêm." | PASS | FAIL | Người | Judge dừng ở tín hiệu bề mặt "Dạ, vui lòng". Rubric: chấm **cả câu**, câu mệnh lệnh/gạt khách ("không cần nhắn thêm") → FAIL dù mở đầu lịch sự. |
| 4 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Judge phạt "thiếu xin lỗi". Rubric ghi rõ: xin lỗi **không bắt buộc**; ngắn, đủ ý, lễ phép = PASS. |
| 5 | tone H-051 "Dạ, LogiX đã refund 90.000đ…" | FAIL | PASS | Người | Rubric thêm whitelist thuật ngữ CS LogiX cho phép ("refund", "ship", "voucher") — không phạt tiếng Anh trong whitelist. |
| 6 | tone H-063 "…đã hoàn 20.000đ và sẽ hoàn thêm…" | PASS | FAIL | Người (nhưng không phải lỗi tone) | Hứa hẹn ngoài kết quả hệ thống là lỗi **nội dung/tiền**, không phải giọng điệu → chuyển sang grader code (FM-08: reply phải khớp ledger), bỏ khỏi phạm vi judge tone để rubric không lẫn hai tiêu chí. |
| 7 | tone H-070 "…cho đơn O-909 ạ 😂😂" | PASS | FAIL | Người | Rubric: emoji cười/đùa trong ngữ cảnh khiếu nại → FAIL. |
| 8 | tone H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn…" | FAIL | PASS | **Judge** — nhãn người sai | Note: người đọc nhầm ticket. **Sửa nhãn vàng** H-081 → FAIL, ghi lý do và người duyệt lại; sau khi sửa, tính lại κ/P/R (fp 4→3, tp 24→25). Thêm bước double-label cho case từ chối hoàn tiền. |
| 9 | tone H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ…" | FAIL | PASS | Người | Lỗi gõ lặp từ không làm sai giọng điệu. Rubric: lỗi chính tả nhỏ không đổi nghĩa → không FAIL tone (theo dõi riêng nếu cần). |
| 10 | tone H-094 "Da, LogiX da hoan 40.000đ… xin loi…" | PASS | FAIL | Người | Rubric: tiếng Việt mất dấu / dịch máy → FAIL (khách đọc như tin rác). Có thể bắt bằng code (tỉ lệ ký tự có dấu) thay vì judge. |
| 11 | helpful HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." | PASS | FAIL (sai tiền; ledger 40.000đ) | Người | Judge **không được thấy ledger** nên không thể biết số sai. Không sửa được bằng rubric → chấm bằng code (`reply_amount_matches_ledger`). |
| 12 | helpful HL-016 reply dài, xin lỗi 2 lần, "đã hoàn 55.000đ" (ledger 35.000đ) | PASS | FAIL | Người | Thiên lệch độ dài/xin lỗi: reply bị judge bỏ sót dài TB 156 ký tự, reply bị bắt TB 31 ký tự. Rubric: lời xin lỗi không cộng điểm helpful; số tiền vẫn phải chấm bằng code. |
| 13 | helpful HL-043 xin lỗi dài, "đã hoàn 35.000đ cho đơn O-202" (ledger 20.000đ) | PASS | FAIL | Người | Cùng mẫu với FM-08 trong eval set (reply 35k ≠ ledger 20k, C-008). Bằng chứng judge không thay được grader code cho tiền. |
| 14 | helpful HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL (sai xưng hô) | Người | Đây là lỗi tone, không phải helpful → để judge tone (đã calibrated) chấm; rubric helpful bỏ tiêu chí xưng hô để tránh chồng lấn. |
| 15 | helpful HL-019 "Đơn O-909 không được hoàn." | FAIL | FAIL (giọng cụt) | Đồng ý | Ghi nhận: 9/9 FAIL judge bắt được đều là reply **ngắn** (lạc đề, cụt, không hỏi mã đơn) — judge chỉ học tín hiệu "ngắn = không helpful". |

## Kết luận

- **tone_ok: dùng** (κ 0.757, P 0.857, R 0.8 đều trên sàn). Dùng như metric **non-blocking**, luôn báo kèm tỉ lệ đã hiệu chỉnh Rogan-Gladen (0.28 → 0.30) vì judge vẫn bỏ sót 6/30 FAIL (chủ yếu xưng hô suồng sã) và báo nhầm 4/70. Áp dụng 8 sửa đổi rubric ở trên, sửa nhãn H-081, rồi calibrate lại trên bộ nhãn mới.
- **helpful: loại khỏi gate.** Ma trận 9/0/21/70: precision 1.0 trông đẹp nhưng **recall 0.3** — judge bỏ sót 21/30 FAIL, trong đó **18/18 lỗi "sai tiền"** (judge không có ledger) và 3/3 lỗi xưng hô. Judge thực chất chỉ phát hiện reply ngắn/cụt. Dùng nó làm gate sẽ cho qua đúng loại lỗi đắt nhất (FM-08: nói sai số tiền với khách). κ 0.375 < 0.6 xác nhận đồng thuận yếu.
- Rogan-Gladen của helpful cũng ra 0.30, nhưng con số đó dựa trên sensitivity 0.3 ước lượng từ chính 30 FAIL này — sai số rất lớn; hiệu chỉnh không biến judge kém thành judge dùng được.
- Thay thế: **tiền và approval luôn chấm bằng code** (`refund_amount_correct`, `approval_bypass`, metric FM-08 so reply với ledger). Phần "helpful" còn lại (hỏi lại mã đơn khi thiếu, không lạc đề) có thể chấm bằng code theo status (`needs_info` phải hỏi mã đơn) hoặc viết lại rubric rồi calibrate lại.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng mỗi tiêu chí); cần nhãn người mới để có held-out thật; sửa rubric xong phải đo lại κ/P/R trên tập chưa thấy.
