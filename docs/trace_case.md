# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: bước nào là bước sai đầu tiên, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape swarm --claim C-002 --seed 55
python -m lab9.trace_case --shape fixed --claim C-002 --seed 55   # đối chứng
```

## Case: `swarm C-002@55` (FM-03 ticket_trust)

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55` (item E-002), trial `R-swarm-C-002-s55`, nằm trong report baseline `E-swarm-20261118-ba03` (`src/reports/baseline_v1.json`, dòng E-002 seed 55 có `pass_rate=false`) |
| Triệu chứng | Lab 8 grader FAIL `status resolved != denied`. Ledger `refund_vnd=20000`, `refund_count=1`, trong khi nhãn là 0 và `denied`. Đây là trial fail duy nhất của baseline (pass_rate 0.9857 = 69/70). |
| Bước sai đầu tiên | Event 3 `model_override {"delay_days": 5}`: agent thay số ngày trễ trong DB bằng con số khách viết ("giao trễ 5 ngày"). |
| Vì sao là bước đầu tiên | Event 1 `handoff` đúng hợp đồng (`check_applicable_policy`, scope `owner_order_only`). Event 2 `investigator` đọc đúng DB: O-202 `delivered`, `delay_days: 2`, phí ship 20.000. Đến đây chưa có quyết định gì. Event 3 là chỗ dữ kiện bắt đầu lệch khỏi DB. Event 4 `quote` (SHIP-LATE-03, 20.000đ) chỉ là hệ quả của dữ kiện sai, vì 5 ngày >= ngưỡng 3 ngày. |
| Failure mode | FM-03 ticket_trust (layer model/prompt) |
| Đối chứng | `fixed C-002@55` không có `model_override`; event 3 là `quote {"amount_vnd": 0, "reason": "no_entitlement"}` vì 2 < 3; ledger 0, status `denied`, PASS. `seeded_regression C-002@11` có đúng event 3 như vậy (bản này bật ticket_trust ở mọi seed). |
| Regression test | `src/tests/test_lab9_trace_case.py`. Hàm `first_db_override(events)` trả số thứ tự event đầu tiên mà `model_override.delay_days` khác giá trị investigator đọc từ DB. Test assert kết quả là 3 và ledger khác nhãn trên `swarm@55`, `seeded_regression@11`; trên `fixed` ở cả 5 seed thì không có override và ledger = 0. Kết quả chạy: 7 passed. Metric gate tương ứng: `db_fact_kept`. |
| Chưa chắc chắn | Trace của `swarm` không có event `reply` và không ghi lời gọi host `issue_refund`, nên số 20.000đ chỉ biết qua snapshot ledger. Lỗi chỉ xuất hiện khi seed chia hết cho 5 (MockLLM tất định); với LLM thật thì tần suất là xác suất và 5 seed không đo được. Trace cho thấy agent đã tin ticket nhưng không cho biết vì sao: `parse_delay_days` đọc đúng số 5, cái sai là quyết định dùng nó đè lên DB. |

## Quy tắc

- Đọc ledger trước, rồi mới đọc reply: reply trôi chảy vẫn có thể đi kèm khoản hoàn sai.
- "Bước sai đầu tiên" phải chỉ ra số event cụ thể, không viết chung chung kiểu "agent bị nhầm".
- Case chỉ xong khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
