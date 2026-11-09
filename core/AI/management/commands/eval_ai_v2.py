import json
import statistics
import time
from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from AI.v2 import planner
from AI.v2.pipeline import _resolve_call, answer

QUESTIONS = Path(__file__).resolve().parents[2] / "v2" / "eval_questions.json"


class Command(BaseCommand):
    help = (
        "Score the v2 assistant on AI/v2/eval_questions.json: question kind, tool choice and entity "
        "resolution. With --full, also generate each answer and check its numbers against the data."
    )

    def add_arguments(self, parser):
        parser.add_argument("--full", action="store_true", help="Also run the full pipeline for every question.")
        parser.add_argument("--only", help="Only questions containing this text.")

    def handle(self, *args, full=False, only=None, **options):
        cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
        if only:
            cases = [c for c in cases if only.lower() in c["q"].lower()]
        totals = {"kind": 0, "tools": 0, "entities": 0, "entity_cases": 0, "verified": 0, "errors": 0}
        latencies = []

        for case in cases:
            started = time.monotonic()
            plan = async_to_sync(planner.plan)(case["q"])
            plan_ms = int((time.monotonic() - started) * 1000)
            tools = sorted({call["tool"] for call in plan.calls})
            kind_ok = plan.kind == case["kind"]
            tools_ok = set(case["tools"]) <= set(tools) if case["tools"] else not tools

            resolved_names = {}
            for call in plan.calls:
                _, _, resolved = async_to_sync(_resolve_call)(call)
                for item in resolved:
                    resolved_names.setdefault(item["arg"], []).append(item["match"]["name"])
            expected = case.get("entities") or {}
            entities_ok = all(name in resolved_names.get(arg, []) for arg, name in expected.items())

            totals["kind"] += kind_ok
            totals["tools"] += tools_ok
            if expected:
                totals["entity_cases"] += 1
                totals["entities"] += entities_ok

            line = f"{'OK ' if kind_ok and tools_ok and entities_ok else 'BAD'} plan {plan_ms:>5}ms  {case['q'][:52]:52}"
            line += f"  kind={plan.kind}{'' if kind_ok else '(want ' + case['kind'] + ')'} tools={tools}"
            if expected:
                line += f" entities={resolved_names}" + ("" if entities_ok else f" (want {expected})")

            if full:
                started = time.monotonic()
                result = async_to_sync(answer)(case["q"])
                latencies.append(time.monotonic() - started)
                if result.get("type") == "error":
                    totals["errors"] += 1
                    line += "  ANSWER-ERROR"
                else:
                    totals["verified"] += bool(result.get("verified"))
                    line += f"  answer {latencies[-1]:.1f}s verified={result.get('verified')}"
            self.stdout.write(line)

        n = len(cases)
        summary = (f"\nkind {totals['kind']}/{n}   tools {totals['tools']}/{n}   "
                   f"entities {totals['entities']}/{totals['entity_cases']}")
        if full and latencies:
            summary += (f"   verified {totals['verified']}/{n - totals['errors']}   errors {totals['errors']}"
                        f"   answer latency median {statistics.median(latencies):.1f}s max {max(latencies):.1f}s")
        self.stdout.write(self.style.SUCCESS(summary))
