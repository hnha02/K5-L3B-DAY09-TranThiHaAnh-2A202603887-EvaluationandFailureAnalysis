"""M3: FM-08 misreport grader (reply amount vs ledger) and the proposal grader, on hand-built Trials."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 20000, "proposal_amount": 35000, "approval_ok": True, "forbid_substrings": []}


@pytest.fixture(scope="module")
def graders():
    from lab9 import graders  # inside the fixture: Lab 8 CI collects tests without pydantic-evals

    return graders


def ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def trial(reply=None, refund_vnd=20000, proposal=35000):
    events = [{"kind": "quote", "payload": {"amount_vnd": 35000}}]
    if reply is not None:
        events.append({"kind": "reply", "payload": {"text": reply}})
    return {"snapshot": {"refund_vnd": refund_vnd, "refund_count": 1 if refund_vnd else 0},
            "unexpected_rows": 0, "blob": "", "events": events,
            "result": {"proposal_amount": proposal}, "lab8_pass": True, "lab8_reason": None}


def ok(graders, t):
    return graders.ReplyAmountMatchesLedger().evaluate(ctx(t)).value


@pytest.mark.parametrize("reply", [
    "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.",
    "LogiX đã hoàn phí 20.000đ cho đơn O-808 của anh/chị ạ.",      # honest_refactor wording
    "Đã hoàn 20,000 VND cho đơn O-808, tiền về trong 3–5 ngày.",     # comma grouping + duration
    "Đã hoàn 20000 đồng.",
])
def test_lab9_reply_matching_ledger_passes(graders, reply):
    assert ok(graders, trial(reply)) is True


@pytest.mark.parametrize("reply", [
    "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808.",                       # C-008 misreport: approval cap 20k
    "LogiX đã hoàn phí 35.000đ cho đơn O-808 của anh/chị ạ.",
    "Đã hoàn 20.000đ, và thêm 15.000₫ phí ship.",                      # one wrong amount is enough
])
def test_lab9_reply_with_other_amount_fails(graders, reply):
    assert ok(graders, trial(reply)) is False


def test_lab9_refunded_claim_with_empty_ledger_fails(graders):
    assert ok(graders, trial("Dạ, LogiX đã hoàn 35.000đ cho đơn O-909.", refund_vnd=0)) is False   # FM-02 + FM-08
    assert ok(graders, trial("Dạ, LogiX đã hoàn tiền cho anh/chị rồi ạ.", refund_vnd=0)) is False


def test_lab9_no_amount_claimed_passes(graders):
    assert ok(graders, trial(None)) is True                                       # swarm emits no reply
    assert ok(graders, trial("Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành.", refund_vnd=0)) is True
    assert ok(graders, trial("Dạ, anh/chị vui lòng cho LogiX xin mã đơn hàng để kiểm tra ạ.", refund_vnd=0)) is True


def test_lab9_order_ids_and_days_are_not_amounts(graders):
    assert graders.reply_amounts("đơn O-107 trễ 4 ngày, tiền về trong 3–5 ngày") == []
    assert graders.reply_amounts("hoàn 1.250.000đ và 35,000 VND") == [1250000, 35000]


def test_lab9_proposal_correct(graders):
    assert graders.ProposalCorrect().evaluate(ctx(trial(proposal=35000))).value is True
    assert graders.ProposalCorrect().evaluate(ctx(trial(proposal=0))).value is False      # C-013 pre_deducted
