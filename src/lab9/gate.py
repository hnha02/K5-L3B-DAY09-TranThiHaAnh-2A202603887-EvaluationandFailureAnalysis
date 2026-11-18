"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    man, bman = pr.get("manifest") or {}, base.get("manifest") or {}
    rows, brows = pr.get("rows") or [], base.get("rows") or []

    # 1. metric values must be finite numbers (NaN < min is False, so NaN would sail through)
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and not math.isfinite(v):
            problems.append(f"metric {k} is {v} (not a finite number)")

    # 2. row count = items x seeds, and the manifest still describes the baseline's run
    seeds = man.get("seeds") or []
    if len(rows) != (man.get("items") or 0) * len(seeds):
        problems.append(f"{len(rows)} rows != {man.get('items')} items x {len(seeds)} seeds")
    if bman and (man.get("items"), list(seeds)) != (bman.get("items"), list(bman.get("seeds") or [])):
        problems.append(f"manifest items/seeds {man.get('items')}/{seeds} differ from the baseline's "
                        f"{bman.get('items')}/{bman.get('seeds')}")

    # 3. the exact (item, seed) set, no duplicates (a passing row copied over a failing one keeps the count)
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dups = sorted({k for k in keys if keys.count(k) > 1}, key=str)
    if dups:
        problems.append(f"duplicate (item, seed) rows: {dups[:5]}")
    bkeys = {(r.get("item_id"), r.get("seed")) for r in brows}
    if brows and set(keys) != bkeys:
        missing, extra = sorted(bkeys - set(keys), key=str), sorted(set(keys) - bkeys, key=str)
        problems.append(f"(item, seed) set differs from baseline: missing {missing[:5]}, extra {extra[:5]}")

    # 4. no crashed graders: evaluator failures, or a graded metric missing / None on a row
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s), first: {pr['evaluator_failures'][0]}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    holes = [(r.get("item_id"), r.get("seed"), m) for r in rows for m in graded if r.get(m) is None]
    if holes:
        problems.append(f"{len(holes)} graded value(s) missing/None, first: {holes[0]}")

    # 4b. headline metrics must be what the rows say (a hand-edited or stale metrics block)
    if rows and not holes:
        ids = [m for m in graded if all(m in r for r in rows)]
        rows_c = [{**r, "cost": r.get("cost", 0.0)} for r in rows]
        try:
            again = aggregate(rows_c, ids, k_values=spec.get("pass_k", []))
        except Exception as e:  # noqa: BLE001 -- an unreadable report is untrustworthy, not a crash
            problems.append(f"cannot recompute metrics from rows: {e!r}")
            again = {}
        for k, v in again.items():
            if k == "cost_per_success" and not all("cost" in r for r in rows):
                continue
            got = (pr.get("metrics") or {}).get(k)
            if k in (pr.get("metrics") or {}) and isinstance(v, (int, float)) and isinstance(got, (int, float)) \
                    and math.isfinite(got) and abs(v - got) > 1e-3:
                problems.append(f"metric {k}={got} does not match its rows ({v})")

    # 5. ratchet: thresholds only get stricter (applied whenever base_spec is given -- the gate already
    #    requires the same eval-set sha, so renaming eval_set_version cannot dodge it)
    if base_spec is not None:
        problems += _ratchet(base_spec, spec)

    # 6. slice tags: identical to the baseline's per item, and consistent across an item's seeds
    def tags(rs: list[dict]) -> tuple[dict, set]:
        out: dict = {}
        mixed: set = set()
        for r in rs:
            t = tuple(sorted(r.get("slices") or []))
            if r.get("item_id") in out and out[r.get("item_id")] != t:
                mixed.add(r.get("item_id"))
            out.setdefault(r.get("item_id"), t)
        return out, mixed
    ptags, pmixed = tags(rows)
    btags, _ = tags(brows)
    if pmixed:
        problems.append(f"slice tags differ between seeds of {sorted(pmixed, key=str)[:5]}")
    moved = sorted((i for i in ptags if i in btags and ptags[i] != btags[i]), key=str)
    if moved:
        problems.append(f"slice tags differ from baseline for {moved[:5]}")
    return problems


def _ratchet(old: dict, new: dict) -> list[str]:
    """Loosening between the baseline's spec (old) and the PR's spec (new)."""
    out: list[str] = []

    def cmp(where: str, o: dict, n: dict | None) -> None:
        if n is None:
            out.append(f"ratchet: {where} removed")
            return
        ot, nt = o.get("threshold", o), n.get("threshold", n)
        for key in ("min",):
            if key in ot and (key not in nt or nt[key] < ot[key]):
                out.append(f"ratchet: {where} {key} {ot[key]} -> {nt.get(key)}")
        for key in ("max", "max_increase"):
            if key in ot and (key not in nt or nt[key] > ot[key]):
                out.append(f"ratchet: {where} {key} {ot[key]} -> {nt.get(key)}")
        if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
            out.append(f"ratchet: {where} dropped no_significant_drop")
        if o.get("blocking") and not n.get("blocking"):
            out.append(f"ratchet: {where} no longer blocking")
        if "metric" in o and n.get("metric") != o.get("metric"):
            out.append(f"ratchet: {where} metric {o.get('metric')} -> {n.get('metric')}")

    new_m = {m["id"]: m for m in new.get("metrics") or []}
    for m in old.get("metrics") or []:
        cmp(f"metric {m['id']}", m, new_m.get(m["id"]))
    new_s = {(s.get("name"), s.get("metric")): s for s in new.get("slices") or []}
    for s in old.get("slices") or []:
        cmp(f"slice {s.get('name')}/{s.get('metric')}", s, new_s.get((s.get("name"), s.get("metric"))))
    for key in ("seeds", "eval_set", "labels"):
        if key in old and new.get(key) != old.get(key):
            out.append(f"ratchet: spec {key} changed {old.get(key)} -> {new.get(key)}")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note, val = "ok", "", None
        if not a:
            verdict, note = "fail", "empty slice"            # an empty slice proves nothing
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in s and val < s["min"]:
                verdict = "fail"
            if "max" in s and val > s["max"]:
                verdict = "fail"
            if s.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}] n={len(keys)}"
                    if hi < 0:
                        verdict = "fail"
                else:
                    verdict, note = "fail", "no items shared with baseline"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = "ok" if verdict == "ok" else ("BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<34} {val!s:<8} {json.dumps(th):<40} {note:<34} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
