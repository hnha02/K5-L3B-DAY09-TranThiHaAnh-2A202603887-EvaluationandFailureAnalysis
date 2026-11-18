"""Regression test for the trace case in docs/trace_case.md (FM-03 ticket_trust).

swarm C-002@55: event 3 `model_override {"delay_days": 5}` overrides the DB value (O-202 delay_days=2),
so the quote becomes entitled and 20.000đ lands in the ledger where the label says 0.
The assertion: the delay_days the agent quotes on must equal the DB value the investigator read.
"""
import pytest

pytestmark = pytest.mark.student


def first_db_override(events):
    """Index (1-based) of the first event that replaces a DB fact with another value, else None."""
    db_delay = None
    for i, e in enumerate(events, 1):
        payload = e.get("payload") or {}
        if e.get("kind") == "investigator":
            db_delay = ((payload.get("lookup_order") or {}).get("order") or {}).get("delay_days")
        if e.get("kind") == "model_override" and "delay_days" in payload and payload["delay_days"] != db_delay:
            return i
    return None


def run(shape, claim, seed):
    # Imported here: the Lab 8 CI collects tests without lab9's dependencies installed.
    from lab9.trace_case import investigate

    case = investigate(shape, claim, seed)
    return case["trial"], case["label"]


@pytest.mark.parametrize("shape, seed", [("swarm", 55), ("seeded_regression", 11)])
def test_lab9_trace_case_catches_ticket_trust(shape, seed):
    trial, label = run(shape, "C-002", seed)
    assert first_db_override(trial["events"]) == 3            # first wrong step = event 3
    assert trial["snapshot"]["refund_vnd"] != label["refund_vnd"]
    assert not trial["lab8_pass"]


@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_lab9_trace_case_fixed_keeps_db_fact(seed):
    trial, label = run("fixed", "C-002", seed)
    assert first_db_override(trial["events"]) is None
    assert trial["snapshot"]["refund_vnd"] == label["refund_vnd"] == 0
    assert trial["result"]["status"] == label["status"] == "denied"
    assert trial["lab8_pass"]
