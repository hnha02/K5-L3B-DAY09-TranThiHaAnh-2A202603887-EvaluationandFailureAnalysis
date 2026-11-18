# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape swarm --claim C-002 --seed 55
python -m lab9.trace_case --shape fixed --claim C-002 --seed 55   # đối chứng
```

## Case: `swarm C-002@55` — FM-03 ticket_trust

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55` (item E-002), trial run `R-swarm-C-002-s55`; report baseline **`E-swarm-20261118-ba03`** (`src/reports/baseline_v1.json`, row E-002 seed 55 `pass_rate=false`) |
| Triệu chứng | Lab 8 grader FAIL `status resolved != denied`. Ledger `refund_vnd=20000`, `refund_count=1`; nhãn `refund_vnd=0`, `status=denied`. Đây là trial fail duy nhất của baseline `swarm` (pass_rate 0.9857 = 69/70). |
| Bước sai đầu tiên | **Event 3 `model_override` `{"delay_days": 5}`** — agent thay số ngày trễ của DB bằng số khách viết trong ticket ("giao trễ 5 ngày"). |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng hợp đồng (`check_applicable_policy`, scope `owner_order_only`). Event 2 `investigator` đọc đúng DB: O-202 `delivered`, `delay_days: 2`, phí ship 20.000. Tới đây chưa có quyết định nào. Event 3 là chỗ đầu tiên dữ kiện lệch khỏi DB; event 4 `quote` (`SHIP-LATE-03`, 20.000đ, `entitled`) chỉ là hệ quả đúng logic của dữ kiện sai (min_delay_days 3 ≤ 5). |
| Failure mode | **FM-03** ticket_trust (layer model/prompt) — `docs/failure_taxonomy.md` |
| Đối chứng | `fixed C-002@55`: không có event `model_override`; event 3 `quote` `{"amount_vnd": 0, "reason": "no_entitlement"}` vì delay 2 < 3; ledger 0, status `denied`, lab8 PASS. `seeded_regression C-002@11` có đúng cùng event 3 (`ticket_trust` bật ở mọi seed). |
| Regression test | `src/tests/test_lab9_trace_case.py`: `first_db_override(events)` trả số event đầu tiên mà `model_override.delay_days` khác `delay_days` investigator đọc từ DB. `test_lab9_trace_case_catches_ticket_trust` assert = 3 và ledger ≠ nhãn trên `swarm@55` và `seeded_regression@11`; `test_lab9_trace_case_fixed_keeps_db_fact` assert `None` + ledger 0 trên `fixed` ở cả 5 seed. Đã chạy: 7 passed. Metric gate tương ứng: `db_fact_kept`. |
| Chưa chắc chắn | (1) Trace của `swarm` không có event `reply` và không ghi lời gọi host `issue_refund`, nên số 20.000đ trong ledger chỉ suy ra từ snapshot, không thấy trực tiếp trên trace. (2) Lỗi chỉ xuất hiện khi `seed % 5 == 0` (MockLLM tất định): với LLM thật tần suất override là xác suất, 5 seed không đo được tỉ lệ đó. (3) Trace chỉ chứng minh agent *đã* tin ticket, không cho biết vì sao (prompt hay parser) — `parse_delay_days` đọc đúng "5", lỗi nằm ở quyết định dùng nó đè lên DB. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
