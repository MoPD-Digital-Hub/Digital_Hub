import json
import asyncio
import re
import requests

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):

    # ==========================
    # WebSocket lifecycle
    # ==========================

    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        # Fetch instance ID safely
        self.instance_id = await self.get_instance_id(self.room_name)

        if not self.instance_id:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # # Stream chat history
        # history = await self.get_history(self.instance_id)

        # for entry in history:
        #     await self.send(text_data=json.dumps({
        #         "question": entry["question"],
        #         "response": entry["response"]
        #     }))
        #     await asyncio.sleep(0.05)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # ==========================
    # Incoming messages
    # ==========================

    async def receive(self, text_data):
        from AI.utils import run_chain_stream
        from AI.ai_instance import retriever, llm

        data = json.loads(text_data)
        question_text = data.get("message", "").strip()

        if not question_text:
            return

        # Save question
        await self.save_question(self.instance_id, question_text)

        year_requested = self.extract_year_from_question(question_text)

        docs = retriever.invoke(question_text)

        if docs:
            full_context = await self.create_context(docs, year_requested)
        else:
            full_context = "No relevant indicator found."

        full_response = []

        history = await self.get_history(self.instance_id)
        conversation_list = self.format_history_for_llm(history)

        # STREAM DIRECTLY TO CLIENT
        async for chunk in run_chain_stream(llm, conversation_list, full_context, question_text):
            if not chunk:
                continue

            full_response.append(chunk)

            await self.send(text_data=json.dumps({
                "message": chunk,
                "is_stream": True,
            }))

            # Yield control to event loop 
            await asyncio.sleep(0)

        final_response = "".join(full_response)

        # Save full response
        await self.save_response(self.instance_id, final_response)

        # Explicit end-of-stream signal
        await self.send(text_data=json.dumps({
            "message": "",
            "is_stream": False,
            "is_final": True,
        }))



    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "is_stream": event.get("is_stream", False),
            "is_final": event.get("is_final", False)
        }))

    # ==========================
    # Database helpers
    # ==========================

    @database_sync_to_async
    def get_instance_id(self, room_name):
        from .models import ChatInstance
        instance = ChatInstance.objects.filter(
            id=room_name,
            is_deleted=False
        ).first()
        return instance.id if instance else None

    @database_sync_to_async
    def get_history(self, instance_id):
        from .models import QuestionHistory
        return list(
            QuestionHistory.objects.filter(
                instance_id=instance_id
            ).order_by("created_at")
             .values("question", "response")
        )

    @database_sync_to_async
    def save_question(self, instance_id, question):
        from .models import QuestionHistory
        return QuestionHistory.objects.create(
            instance_id=instance_id,
            question=question
        )

    @database_sync_to_async
    def save_response(self, instance_id, response):
        from .models import QuestionHistory
        last = QuestionHistory.objects.filter(
            instance_id=instance_id
        ).order_by("-created_at").first()
        if last:
            last.response = response
            last.save()

    # ==========================
    # Context building
    # ==========================

    async def create_context(self, docs, year_requested):
        contexts = []

        for doc in docs:
            meta = doc.metadata

            indicator_code = meta.get("code", "")
            unit = meta.get("unit", "")
            name = meta.get("name", "")
            topic = meta.get("topic", "")
            category = meta.get("category", "")
            source = meta.get("source", "")
            kpi_type = meta.get("kpi_type", "")
            parent = meta.get("parent", "")
            version = meta.get("version", "")

            response = await self.fetch_time_series_value(
                indicator_code,
                year_requested
            )

            historical_info = self.format_time_series(
                response,
                year_requested,
                unit
            )

            metadata_info = f"""
<h3>Indicator Metadata</h3>
<p><b>Name:</b> {name}</p>
<p><b>Code:</b> {indicator_code}</p>
<p><b>Topic:</b> {topic}</p>
<p><b>Category:</b> {category}</p>
<p><b>Unit:</b> {unit}</p>
<p><b>Source:</b> {source}</p>
<p><b>KPI Type:</b> {kpi_type}</p>
<p><b>Parent:</b> {parent}</p>
<p><b>Version:</b> {version}</p>
"""

            contexts.append(
                doc.page_content +
                "\n\n" +
                metadata_info +
                "\n\n" +
                historical_info
            )

        return "\n<hr/>\n".join(contexts)

    # ==========================
    # Utilities
    # ==========================

    @database_sync_to_async
    def fetch_time_series_value(self, indicator_code, year):
        url = "https://time-series.mopd.gov.et/api/mobile/annual_value/"
        params = {"code": indicator_code, "year": year}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}

    @staticmethod
    def extract_year_from_question(question):
        match = re.search(r"\b(19|20)\d{2}\b", question)
        return int(match.group()) if match else None

    @staticmethod
    def format_time_series(response, year, unit):
        if not response:
            return "<p>Data not available</p>"

        ts = response.get("time_series")
        if not ts:
            value = response.get("value")
            if value:
                return f"<p>{year}: {value} {unit}</p>"
            return "<p>Data not available</p>"

        output = ""

        for key, label in [
            ("annual", "Annual Data"),
            ("quarter", "Quarterly Data"),
            ("month", "Monthly Data"),
        ]:
            items = ts.get(key, [])
            if items:
                output += f"<h4>{label}</h4>"
                for item in items:
                    output += f"<p>{item}</p>"

        return output or "<p>No historical data available</p>"
    
    def format_history_for_llm(self, history, max_turns=3):
        """
        Convert DB history to LLM-compatible message format.
        Keeps last N conversation turns.
        """
        messages = []
        history = history[-max_turns:]

        for entry in history:
            if entry.get("question"):
                messages.append({
                    "role": "user",
                    "content": entry["question"]
                })

            if entry.get("response"):
                messages.append({
                    "role": "system",
                    "content": entry["response"]
                })

        return messages
