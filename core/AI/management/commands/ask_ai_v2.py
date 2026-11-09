import json

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from AI.models import AnswerTrace
from AI.v2.pipeline import answer


class Command(BaseCommand):
    help = "Ask the v2 assistant a question from the terminal and show the answer and its trace."

    def add_arguments(self, parser):
        parser.add_argument("question")

    def handle(self, *args, question, **options):
        result = async_to_sync(answer)(question)
        trace = AnswerTrace.objects.order_by("-id").first()
        self.stdout.write(self.style.MIGRATE_HEADING("Answer"))
        self.stdout.write(result.get("answer") or result.get("message", ""))
        self.stdout.write(self.style.MIGRATE_HEADING("Trace"))
        self.stdout.write(json.dumps({
            "plan": trace.plan, "resolved": trace.resolved, "tool_calls": trace.tool_calls,
            "unsupported_numbers": trace.unsupported_numbers, "latency_ms": trace.latency_ms,
            "sources": result.get("sources"), "verified": result.get("verified"),
        }, indent=1, ensure_ascii=False, default=str))
