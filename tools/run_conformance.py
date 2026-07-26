#!/usr/bin/env python3
"""Run the html5lib-tests tokenizer suites against rigor.

The suites are vendored under tools/vendor/html5lib-tests (pinned in
tools/vendor/html5lib-tests/PINNED). This driver expands every test case,
hands them all to the rigor-conformance binary as a single JSON job, and
compares the returned token streams against the expected ones.

    python tools/run_conformance.py            # summary
    python tools/run_conformance.py -v         # plus the first failures
    python tools/run_conformance.py --failures 50
    python tools/run_conformance.py --file test1.test

Exit status is 0 when every runnable case passes, 1 otherwise, so this can be
wired straight into CI once the tokenizer is at 100%.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SUITE_DIR = os.path.join(HERE, "vendor", "html5lib-tests")
HARNESS_DIR = os.path.join(ROOT, "conformance")
HARNESS_BIN = os.path.join(
    HARNESS_DIR, "build",
    "rigor_conformance.exe" if os.name == "nt" else "rigor_conformance")

# html5lib names states the way the spec titles them; rigor's harness takes the
# bare name. Every state the suites use is implemented; UNSUPPORTED_STATES
# stays as the hook for reporting any future gap as a skip rather than a
# silent pass.
STATE_MAP = {
    "Data state": "Data",
    "PLAINTEXT state": "PLAINTEXT",
    "RCDATA state": "RCDATA",
    "RAWTEXT state": "RAWTEXT",
    "CDATA section state": "CDATA",
    "Script data state": "Script",
}
UNSUPPORTED_STATES = set()

ESCAPE_RE = re.compile(r"\\u([0-9A-Fa-f]{4})")


def unescape(value):
    """Decode the \\uXXXX escapes used by doubleEscaped test cases."""
    if isinstance(value, str):
        return ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), value)
    if isinstance(value, list):
        return [unescape(item) for item in value]
    if isinstance(value, dict):
        return {unescape(k): unescape(v) for k, v in value.items()}
    return value


def merge_characters(tokens):
    """html5lib compares character runs, not individual character tokens."""
    merged = []
    for token in tokens:
        if (token[0] == "Character" and merged and merged[-1][0] == "Character"):
            merged[-1] = ["Character", merged[-1][1] + token[1]]
        else:
            merged.append(list(token))
    return merged


def normalize_expected(output):
    tokens = [t for t in output if t != "ParseError"]
    return merge_characters(tokens)


def load_cases(only_file=None):
    cases = []
    skipped = []
    names = sorted(f for f in os.listdir(SUITE_DIR) if f.endswith(".test"))
    if only_file:
        names = [n for n in names if n == only_file]
        if not names:
            raise SystemExit(f"no vendored suite named {only_file!r}")
    for name in names:
        with open(os.path.join(SUITE_DIR, name), "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for test in payload.get("tests", []):
            double = test.get("doubleEscaped", False)
            source = unescape(test["input"]) if double else test["input"]
            expected = normalize_expected(
                unescape(test["output"]) if double else test["output"])
            errors = [e["code"] for e in test.get("errors", [])]
            for state in test.get("initialStates", ["Data state"]):
                label = f"{name}: {test['description']} [{state}]"
                if state in UNSUPPORTED_STATES:
                    skipped.append(label)
                    continue
                if state not in STATE_MAP:
                    skipped.append(label)
                    continue
                cases.append({
                    "label": label,
                    "input": source,
                    "state": STATE_MAP[state],
                    "lastStartTag": test.get("lastStartTag", ""),
                    "expected": expected,
                    "expected_errors": errors,
                    "has_error_data": "errors" in test,
                })
    return cases, skipped


def run_harness(cases):
    if not os.path.isfile(HARNESS_BIN):
        raise SystemExit(
            f"missing {HARNESS_BIN}\nbuild it first: cd conformance && mortc build")
    job = json.dumps(
        {"cases": [{"input": c["input"], "state": c["state"],
                    "lastStartTag": c["lastStartTag"]} for c in cases]},
        ensure_ascii=True)
    process = subprocess.run(
        [HARNESS_BIN], input=job.encode("ascii"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        sys.stderr.write(process.stderr.decode("utf-8", "replace"))
        raise SystemExit(f"harness exited {process.returncode}")
    lines = [line for line in process.stdout.decode("ascii").splitlines() if line]
    if len(lines) != len(cases):
        raise SystemExit(
            f"harness returned {len(lines)} results for {len(cases)} cases")
    return [json.loads(line) for line in lines]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show failing cases")
    parser.add_argument("--failures", type=int, default=10,
                        help="how many failures to show (default 10)")
    parser.add_argument("--file", help="run a single vendored suite")
    parser.add_argument("--errors", action="store_true",
                        help="show parse-error mismatches instead of token ones")
    args = parser.parse_args()

    cases, skipped = load_cases(args.file)
    results = run_harness(cases)

    by_suite = {}
    failures = []
    error_failures = []
    error_checked = 0
    error_passed = 0
    for case, result in zip(cases, results):
        suite = case["label"].split(":", 1)[0]
        stats = by_suite.setdefault(suite, [0, 0])
        stats[1] += 1
        got = merge_characters(result["tokens"])
        ok = got == case["expected"]
        if ok:
            stats[0] += 1
        else:
            failures.append((case, got))
        if case["has_error_data"]:
            error_checked += 1
            if sorted(result["errors"]) == sorted(case["expected_errors"]):
                error_passed += 1
            else:
                error_failures.append((case, result["errors"]))

    total = len(cases)
    passed = sum(stats[0] for stats in by_suite.values())

    print(f"rigor tokenizer vs html5lib-tests\n")
    width = max(len(name) for name in by_suite) if by_suite else 10
    for suite in sorted(by_suite):
        good, count = by_suite[suite]
        pct = 100.0 * good / count if count else 0.0
        print(f"  {suite:<{width}}  {good:>5}/{count:<5} {pct:6.2f}%")
    pct = 100.0 * passed / total if total else 0.0
    print(f"\n  {'TOTAL':<{width}}  {passed:>5}/{total:<5} {pct:6.2f}%")
    if error_checked:
        epct = 100.0 * error_passed / error_checked
        print(f"  {'parse errors':<{width}}  {error_passed:>5}/{error_checked:<5} "
              f"{epct:6.2f}%  (codes only; rigor records byte offsets, not line/col)")
    if skipped:
        print(f"  {'skipped':<{width}}  {len(skipped):>5}        "
              f"(states rigor does not implement)")

    if args.errors and error_failures:
        from collections import Counter
        missing = Counter()
        spurious = Counter()
        for case, got in error_failures:
            want = Counter(case["expected_errors"])
            have = Counter(got)
            missing.update(want - have)
            spurious.update(have - want)
        print("\nparse-error codes rigor fails to report:")
        for code, count in missing.most_common():
            print(f"  {count:>5}  {code}")
        print("\nparse-error codes rigor reports but the suite does not expect:")
        for code, count in spurious.most_common():
            print(f"  {count:>5}  {code}")
        print(f"\nfirst {min(args.failures, len(error_failures))} mismatches:\n")
        for case, got in error_failures[:args.failures]:
            print(f"  {case['label']}")
            print(f"    input    {case['input']!r}")
            print(f"    expected {case['expected_errors']}")
            print(f"    got      {got}")
            print()
    elif args.verbose and failures:
        print(f"\nfirst {min(args.failures, len(failures))} failures:\n")
        for case, got in failures[:args.failures]:
            print(f"  {case['label']}")
            print(f"    input    {case['input']!r}")
            print(f"    expected {case['expected']}")
            print(f"    got      {got}")
            print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
