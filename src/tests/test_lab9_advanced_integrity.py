"""M7 extras: integrity checks beyond the public vectors (duplicate rows, failures on a green run,
metrics that do not match their rows, relabelled slices, ratchet on slices / renamed version)."""
import copy

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": i != 3 or s != 2,
         "slices": ["money_movement"] if i < 2 else []} for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "seeds": [1, 2],
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.95, "blocking": True}]}


def report(rows=None, metrics=None, failures=()):
    rows = copy.deepcopy(ROWS if rows is None else rows)
    return {"manifest": {"eval_set_sha": "x", "items": 4, "seeds": [1, 2]}, "rows": rows,
            "metrics": metrics or {"pass_rate": 0.875}, "evaluator_failures": list(failures)}


@pytest.fixture(scope="module")
def gate():
    from lab9 import gate

    return gate


def test_advanced_clean_report_is_trusted(gate):
    assert gate.integrity_check(report(), report(), SPEC, SPEC) == []


def test_advanced_duplicate_row_replacing_a_failure(gate):
    rows = copy.deepcopy(ROWS)
    rows[7] = dict(rows[6])                       # E-003@2 (fail) replaced by a copy of E-003@1 (pass)
    assert gate.integrity_check(report(rows, {"pass_rate": 1.0}), report(), SPEC)


def test_advanced_evaluator_failures_on_green_run(gate):
    assert gate.integrity_check(report(failures=["E-001@1:X:boom"]), report(), SPEC)


def test_advanced_missing_graded_value(gate):
    rows = copy.deepcopy(ROWS)
    del rows[7]["pass_rate"]
    assert gate.integrity_check(report(rows), report(), SPEC)


def test_advanced_metric_not_matching_rows(gate):
    assert gate.integrity_check(report(metrics={"pass_rate": 1.0}), report(), SPEC)


def test_advanced_slice_relabel_and_mixed_tags(gate):
    moved = copy.deepcopy(ROWS)
    for r in moved:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert gate.integrity_check(report(moved), report(), SPEC)
    mixed = copy.deepcopy(ROWS)
    mixed[0]["slices"] = []                       # E-000@1 untagged, E-000@2 tagged
    assert gate.integrity_check(report(mixed), report(mixed), SPEC)


@pytest.mark.parametrize("loosen", [
    lambda s: s["slices"].clear(),
    lambda s: s["slices"][0].update(min=0.5),
    lambda s: s["slices"][0].update(blocking=False),
    lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
    lambda s: s.update(eval_set_version="v3", slices=[]),    # renaming the version does not reset the ratchet
    lambda s: s.update(seeds=[1]),
])
def test_advanced_ratchet(gate, loosen):
    loose = copy.deepcopy(SPEC)
    loosen(loose)
    assert gate.integrity_check(report(), report(), loose, SPEC)


def test_advanced_stricter_spec_is_fine(gate):
    strict = copy.deepcopy(SPEC)
    strict["metrics"][0]["threshold"]["min"] = 0.85
    strict["slices"].append({"name": "adversarial", "metric": "pass_rate", "min": 0.9, "blocking": True})
    assert gate.integrity_check(report(), report(), strict, SPEC) == []


def test_advanced_empty_slice_blocks(gate):
    spec = dict(SPEC, slices=[{"name": "nope", "metric": "pass_rate", "min": 0.9, "blocking": True}])
    blocked, _ = gate.slice_check(report(), report(), spec)
    assert blocked == ["slice:nope/pass_rate"]
