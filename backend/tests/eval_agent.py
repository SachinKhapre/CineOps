"""Ground-truth eval (§40, §41): runs the agent against an injected incident
and scores what it found against the matching scenarios/incident_*.json.

Load the data for the scenario first -- the incidents live in separate
datasets so each is scored on its own (§39: each injected incident is a test
case):

    python data/generator/generate.py --scale medium --incident c
    python backend/tests/eval_agent.py --scenario c --runs 3

Unlike test_mediadoc_agent.py's self-checks, this calls Gemini for real and
costs API credits -- roughly 8-12 model calls per run. Detection quality is
not deterministic, so a single pass proves little; use --runs to measure how
often it actually lands on the right answer.
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.agents.mediadoc_agent import investigate

SCENARIO_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "generator", "scenarios")
QUESTION = "Something went wrong with our streaming content yesterday. Investigate it."


def _overlaps(a, b):
    """True if two [start, end] hour windows share any hours."""
    if not a or not b or len(a) < 2 or len(b) < 2:
        return False
    return max(a[0], b[0]) <= min(a[1], b[1])


def score(result: dict, truth: dict) -> dict:
    """Scores one investigation against ground truth. §39: the agent need not
    match wording, only identify the correct causal candidate.

    Which dimension checks apply comes from the scenario's
    affected_dimensions, because the incidents are localized differently --
    Incident A to a device/region/quality/hour slice, Incident C to a single
    title regardless of those.
    """
    detection = result.get("detection") or {}
    segment = detection.get("most_affected") or {}
    dims = truth["affected_dimensions"]
    evidence = result.get("evidence") or []
    conclusion = result.get("conclusion") or {}
    # The content_id may be named anywhere in the narrative, not just in the
    # segment, so search the whole conclusion for the content checks.
    narrative = " ".join([
        conclusion.get("root_cause") or "",
        conclusion.get("recommendation") or "",
        json.dumps(segment),
    ]).lower()

    checks = {"day": detection.get("anomaly_day") == truth["incident_day"]}

    if "device_type" in dims:
        checks["device_type"] = segment.get("device_type") == dims["device_type"]
    if "region" in dims:
        checks["region"] = segment.get("region") == dims["region"]
    if "quality" in dims:
        checks["quality"] = segment.get("quality") in dims["quality"]
    if "hour_range" in dims:
        checks["hour_window"] = _overlaps(segment.get("hour_range"), dims["hour_range"])
    if "content_id" in dims:
        checks["content_id"] = dims["content_id"].lower() in narrative

    checks["root_cause"] = any(k in narrative for k in truth["root_cause_keywords"])
    # §40 false positives: for a content anomaly, blaming the delivery path is
    # the wrong answer even though the metrics moved.
    if truth.get("wrong_cause_keywords"):
        checks["not_misattributed"] = not any(k in narrative for k in truth["wrong_cause_keywords"])
    # §40 evidence quality: it should both back the conclusion it kept AND
    # actively rule the alternatives out.
    checks["cited_evidence"] = any(e.get("supported") for e in evidence)
    checks["rejected_alternatives"] = any(not e.get("supported") for e in evidence)
    return checks


def _found(result: dict) -> str:
    segment = (result.get("detection") or {}).get("most_affected") or {}
    day = (result.get("detection") or {}).get("anomaly_day", "?")
    return (f"{day} / {segment.get('device_type', '?')} / {segment.get('region', '?')} / "
            f"{segment.get('quality', '?')} / {segment.get('hour_range')}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1, help="investigations to run (each costs API credits)")
    parser.add_argument("--scenario", choices=["a", "c"], default="a", help="which injected incident to score against")
    args = parser.parse_args()

    truth = json.load(open(os.path.join(SCENARIO_DIR, f"incident_{args.scenario}.json")))
    dims = ", ".join(f"{k}={v}" for k, v in truth["affected_dimensions"].items())
    print(f"Ground truth {truth['incident_id']} on {truth['incident_day']}: {dims}")
    # Nothing here can tell whether the matching dataset is actually loaded, so
    # say what it should be -- a total wipeout usually means the wrong one is.
    print(f"Expecting data from: generate.py --scale medium --incident {args.scenario}\n")

    all_checks, all_stats, failures = [], [], 0
    for run in range(1, args.runs + 1):
        result = await investigate(QUESTION)
        stats = result.get("stats", {})
        all_stats.append(stats)

        if "error" in result:
            failures += 1
            print(f"Run {run}/{args.runs}: FAILED in phase '{result.get('phase')}' -- {result['error']}")
            all_checks.append({k: False for k in score({}, truth)})
            continue

        checks = score(result, truth)
        all_checks.append(checks)
        passed = sum(checks.values())
        print(f"Run {run}/{args.runs}: {passed}/{len(checks)} checks | "
              f"{stats.get('queries', '?')} queries, {stats.get('model_calls', '?')} model calls, "
              f"{stats.get('seconds', '?')}s")
        print(f"  found: {_found(result)}")
        print(f"  confidence: {result.get('confidence', {}).get('band', '?')}")
        for name, ok in checks.items():
            if not ok:
                print(f"  FAIL {name}")

    print(f"\n--- Summary over {args.runs} run(s) ---")
    for name in all_checks[0]:
        hits = sum(1 for c in all_checks if c[name])
        print(f"  {name:<22} {hits}/{args.runs}")
    full = sum(1 for c in all_checks if all(c.values()))
    print(f"  {'ALL CHECKS':<22} {full}/{args.runs}")
    if failures:
        print(f"  ({failures} run(s) errored out mid-investigation)")
    if all_stats:
        avg = lambda k: round(sum(s.get(k, 0) for s in all_stats) / len(all_stats), 1)
        print(f"  avg: {avg('queries')} queries, {avg('model_calls')} model calls, {avg('seconds')}s")


if __name__ == "__main__":
    asyncio.run(main())
