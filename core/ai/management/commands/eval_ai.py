import json
import statistics
import time
from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from ai.engine import planner, verify
from ai.engine.pipeline import _resolve_call, answer
from ai.models import AnswerTrace

QUESTIONS = Path(__file__).resolve().parents[2] / "engine" / "eval_questions.json"


class Command(BaseCommand):
    help = (
        "Score the assistant on AI/engine/eval_questions.json: question kind, tool choice, entity "
        "resolution and answer language. With --full, also generate each answer and check its numbers "
        "against the data, and (Amharic) that no other script reached the answer or had to be removed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--full", action="store_true", help="Also run the full pipeline for every question.")
        parser.add_argument("--only", help="Only questions containing this text.")

    def handle(self, *args, full=False, only=None, **options):
        cases = json.loads(QUESTIONS.read_text(encoding="utf-8"))
        if only:
            cases = [c for c in cases if only.lower() in c["q"].lower()]
        totals = {"kind": 0, "tools": 0, "entities": 0, "entity_cases": 0, "verified": 0, "errors": 0,
                  "language": 0, "language_cases": 0, "search": 0, "search_cases": 0, "amharic_answers": 0, "script_repairs": 0, "script_leaks": 0}
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

            language_ok = plan.language == case.get("language", plan.language)
            # "search": whether the plan should also search the web (mixed questions) or not.
            search_ok = "search" not in case or bool(plan.search_query) == case["search"]
            if "search" in case:
                totals["search_cases"] += 1
                totals["search"] += search_ok
            if case.get("language"):
                totals["language_cases"] += 1
                totals["language"] += language_ok

            totals["kind"] += kind_ok
            totals["tools"] += tools_ok
            if expected:
                totals["entity_cases"] += 1
                totals["entities"] += entities_ok

            good = kind_ok and tools_ok and entities_ok and language_ok and search_ok
            line = f"{'OK ' if good else 'BAD'} plan {plan_ms:>5}ms  {case['q'][:52]:52}"
            line += f"  kind={plan.kind}{'' if kind_ok else '(want ' + case['kind'] + ')'} tools={tools}"
            if not language_ok:
                line += f" language={plan.language} (want {case['language']})"
            if plan.search_query or not search_ok:
                line += f" search={plan.search_query!r}" + ("" if search_ok else f" (want search={case['search']})")
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
                    if plan.language == "Amharic":
                        totals["amharic_answers"] += 1
                        trace = AnswerTrace.objects.order_by("-id").first()
                        if trace and trace.error.startswith("foreign script removed"):
                            totals["script_repairs"] += 1
                            line += "  SCRIPT-REPAIRED"
                        if verify.foreign_script(result.get("answer") or ""):
                            totals["script_leaks"] += 1
                            line += "  SCRIPT-LEAK"
            self.stdout.write(line)

        n = len(cases)
        summary = (f"\nkind {totals['kind']}/{n}   tools {totals['tools']}/{n}   "
                   f"entities {totals['entities']}/{totals['entity_cases']}   "
                   f"language {totals['language']}/{totals['language_cases']}   "
                   f"search {totals['search']}/{totals['search_cases']}")
        if full and latencies:
            summary += (f"   verified {totals['verified']}/{n - totals['errors']}   errors {totals['errors']}"
                        f"   answer latency median {statistics.median(latencies):.1f}s max {max(latencies):.1f}s"
                        f"   amharic: {totals['amharic_answers']} answers, {totals['script_repairs']} repaired, "
                        f"{totals['script_leaks']} with other scripts")
        self.stdout.write(self.style.SUCCESS(summary))
