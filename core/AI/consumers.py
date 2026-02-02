import json
import asyncio
import re
import requests
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from AI.classifier import classify_intent,extract_year_quarter, extract_performance_type
from AI.intents import INTENTS

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
        from .vectorstore import get_retriever
        from .providers import get_llm_instance

        llm = get_llm_instance()
        retriever = get_retriever()

        data = json.loads(text_data)
        question_text = data.get("message", "").strip()

        if not question_text:
            return

        # Save question
        await self.save_question(self.instance_id, question_text)

        year_requested = self.extract_year_from_question(question_text)



        intent = classify_intent(llm, question_text)
        docs = retriever.invoke(question_text)


        if intent == INTENTS["TIME_SERIES"]:
            full_context = await self.create_context(docs, year_requested)
        elif intent == INTENTS["MINISTRY_SCORE"]:
            period_requested = extract_year_quarter(llm, question_text)
            full_context = await self.create_ministry_context(docs, period_requested)
        elif intent == INTENTS["MINISTRY_PERFORMANCE"]:
            period_requested = extract_year_quarter(llm, question_text)
            performance_requested = extract_performance_type(llm, question_text)
            full_context = await self.create_ministry_performance_context(docs, period_requested,performance_requested)
        else:
            full_context = "Please clarify your question related to DPMES indicators."


        full_response = []

        history = await self.get_history(self.instance_id)
        conversation_list = self.format_history_for_llm(history)

        # STREAM DIRECTLY TO CLIENT
        async for chunk in run_chain_stream(llm, conversation_list, full_context, question_text, intent):
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

            indicator_code = meta.get("indicator_code", "")
            annual_measurement_unit = meta.get("annual_measurement_unit", "")
            quarter_measurement_unit = meta.get("quarter_measurement_unit", "")
            month_measurement_unit = meta.get("month_measurement_unit", "")
            name = meta.get("indicator_eng", "")
            topic = meta.get("topic_name", "")
            category = meta.get("category_name", "")
            source = meta.get("source", "")
            kpi_type = meta.get("characteristics", "")
            parent = meta.get("parent", "")

            response = await self.fetch_time_series_value(
                indicator_code,
                year_requested
            )

            historical_info = self.format_time_series(
                response,
                year_requested
            )

            metadata_info = f"""
<h3>Indicator Metadata</h3>
<p><b>Name:</b> {name}</p>
<p><b>Code:</b> {indicator_code}</p>
<p><b>Topic:</b> {topic}</p>
<p><b>Category:</b> {category}</p>
<p><b>Annual Measurement Unit:</b> {annual_measurement_unit}</p>
<p><b>Quarter Measurement Unit:</b> {quarter_measurement_unit}</p>
<p><b>Month Measurement Unit:</b> {month_measurement_unit}</p>
<p><b>Source:</b> {source}</p>
<p><b>KPI Type:</b> {kpi_type}</p>
<p><b>Parent:</b> {parent}</p>
"""

            contexts.append(
                doc.page_content +
                "\n\n" +
                metadata_info +
                "\n\n" +
                historical_info
            )

        return "\n<hr/>\n".join(contexts)
    
    async def create_ministry_context(self, docs, period_requested):
        contexts = []

        for doc in docs:
            meta = doc.metadata or {}

            m_id = meta.get("responsible_ministry_id", "")
            m_name = meta.get("responsible_ministry_eng", "Unknown Ministry")
            m_code = meta.get("responsible_ministry_code", "N/A")
            m_source = meta.get("source", "Ministry of Planning and Development")
            
    
            response = await self.fetch_ministry_score(m_id, year=period_requested['year'], quarter=period_requested['quarter'])
            

            performance_info = self.format_ministry_score(response)

        
            metadata_info = f"""
    <h3>Ministry Metadata</h3>
    <p><b>Ministry Name:</b> {m_name}</p>
    <p><b>Code:</b> {m_code}</p>
    <p><b>Data Source:</b> {m_source}</p>
    <p><b>Entity ID:</b> {m_id}</p>
    """

            contexts.append(
                f"{doc.page_content}\n\n{metadata_info}\n\n{performance_info}"
            )

        return "\n<hr/>\n".join(contexts)
    
    async def create_ministry_performance_context(self, docs, period_requested,performance_requested):
        contexts = []

        for doc in docs:
            meta = doc.metadata or {}

            m_id = meta.get("responsible_ministry_id", "")
            m_name = meta.get("responsible_ministry_eng", "Unknown Ministry")
            m_code = meta.get("responsible_ministry_code", "N/A")
            m_source = meta.get("source", "Ministry of Planning and Development")
            
    
            response = await self.fetch_ministry_performance(m_id, year=period_requested['year'], quarter=period_requested['quarter'], performance_requested = performance_requested)
            

            performance_info = self.format_ministry_performance(response)

        
            metadata_info = f"""
    <h3>Ministry Metadata</h3>
    <p><b>Ministry Name:</b> {m_name}</p>
    <p><b>Code:</b> {m_code}</p>
    <p><b>Data Source:</b> {m_source}</p>
    <p><b>Entity ID:</b> {m_id}</p>
    """

            contexts.append(
                f"{doc.page_content}\n\n{metadata_info}\n\n{performance_info}"
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

    @database_sync_to_async
    def fetch_ministry_score(self,ministry_id, year, quarter):
        url = f"https://dpmes.mopd.gov.et/api/ai/ministry-score/{ministry_id}"
        params = {}
        if year and year.lower() != "null":
            params["year"] = year
        if quarter and quarter.lower() != "null":
            params["quarter"] = quarter

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    
    @database_sync_to_async
    def fetch_ministry_performance(self,ministry_id, year, quarter, performance_requested):
        url = f"https://dpmes.mopd.gov.et/api/ai/ministry-kpi-performance/{ministry_id}"
        params = {}
        if year and year.lower() != "null":
            params["year"] = year
        if quarter and quarter.lower() != "null":
            params["quarter"] = quarter
        if performance_requested:
            params["performance_type"] = performance_requested
            
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        return {}
    
    
    @staticmethod
    def extract_year_from_question(question):
        match = re.search(r"\b(19|20)\d{2}\b", question)
        return int(match.group()) if match else None

    @staticmethod
    def format_time_series(response, year):
        if not response:
            return "<p>Data not available</p>"

        ts = response.get("time_series")
        if not ts:
            value = response.get("value")
            if value:
                return f"<p>{year}: {value}</p>"
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
    
    @staticmethod
    def format_ministry_score(data):
        if not data:
            return "<p>No ministry performance data found.</p>"
        
        ministry_name = data.get("responsible_ministry_eng", "Unknown Ministry")
        code = data.get("code", "N/A")
        total_indicators = data.get("number_of_indicators", 0)
        
        score_card = data.get("ministry_score_card", {})
        overall_score = score_card.get("score", "N/A")
        year = score_card.get("year", "N/A")
        quarter = score_card.get("quarter", "Annual")
        score_color = score_card.get("score_color", "#000000")
        
        header_html = f"""
    <h3>Ministry Performance Overview: {ministry_name} ({code})</h3>
    <p><b>Reporting Period:</b> {year} {f'- {quarter}' if quarter != 'Annual' else ''}</p>
    <p><b>Overall Ministry Score:</b> <span style="color: {score_color}; font-weight: bold;">{overall_score}</span></p>
    <p><b>Performance Status Color:</b> {score_color}</p>
    <p><b>Total Indicators Tracked:</b> {total_indicators}</p>
    <hr/>
    """

        policy_areas = data.get("policy_areas", [])
        table_rows = ""
        for area in policy_areas:
            name = area.get("policy_area_eng", "N/A")
            score = area.get("score", "N/A")
            p_color = area.get("score_color", "")
            
            table_rows += f"<tr><td>{name}</td><td>{score} {f'({p_color})' if p_color else ''}</td></tr>"

        policy_html = f"""
    <h4>Breakdown by Policy Area</h4>
    <table>
        <thead>
            <tr><th>Policy Area</th><th>Score</th></tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    """
        return header_html + policy_html
    
    @staticmethod
    def format_ministry_performance(data):
        if not data or not data.get("kpis"):
            return "<p>No specific indicator performance data found for the selected criteria.</p>"
        
        ministry_name = data.get("responsible_ministry_eng", "Unknown Ministry")
        code = data.get("code", "N/A")
        kpis = data.get("kpis", [])
        
        first_kpi = kpis[0]
        year = first_kpi.get("year", "N/A")
        quarter = first_kpi.get("quarter", "Annual")

        header_html = f"""
    <h3>Indicator Performance List: {ministry_name} ({code})</h3>
    <p><b>Reporting Period:</b> {year} {f'- {quarter}' if quarter != 'Annual' else ''}</p>
    <p><b>Total Indicators in this Category:</b> {len(kpis)}</p>
    <hr/>
    """

        table_rows = ""
        for item in kpis:
            name = item.get("indicator_name", "Unknown Indicator")
            score = item.get("score", "N/A")
            color = item.get("scorecard", "#000000")
            
            table_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{name}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">
                    <span style="color: {color}; font-weight: bold;">{score}%</span>
                </td>
            </tr>"""

        table_html = f"""
    <h4>Detailed Indicator Breakdown</h4>
    <table style="width: 100%; border-collapse: collapse;">
        <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="text-align: left; padding: 8px;">Indicator Name</th>
                <th style="text-align: center; padding: 8px;">Score</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    """
        return header_html + table_html
        
    
    
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



class ChatWebConsumer(AsyncWebsocketConsumer):

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

        # Stream chat history
        history = await self.get_history(self.instance_id)

        for entry in history:
            await self.send(text_data=json.dumps({
                "question": entry["question"],
                "response": entry["response"]
            }))
            await asyncio.sleep(0.05)

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
        from AI.ai_instance import get_retriever, llm

        
        retriever = get_retriever()

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

            indicator_code = meta.get("indicator_code", "")
            annual_measurement_unit = meta.get("annual_measurement_unit", "")
            quarter_measurement_unit = meta.get("quarter_measurement_unit", "")
            month_measurement_unit = meta.get("month_measurement_unit", "")
            name = meta.get("indicator_eng", "")
            topic = meta.get("topic_name", "")
            category = meta.get("category_name", "")
            source = meta.get("source", "")
            kpi_type = meta.get("characteristics", "")
            parent = meta.get("parent", "")

            response = await self.fetch_time_series_value(
                indicator_code,
                year_requested
            )

            historical_info = self.format_time_series(
                response,
                year_requested
            )

            metadata_info = f"""
<h3>Indicator Metadata</h3>
<p><b>Name:</b> {name}</p>
<p><b>Code:</b> {indicator_code}</p>
<p><b>Topic:</b> {topic}</p>
<p><b>Category:</b> {category}</p>
<p><b>Annual Measurement Unit:</b> {annual_measurement_unit}</p>
<p><b>Quarter Measurement Unit:</b> {quarter_measurement_unit}</p>
<p><b>Month Measurement Unit:</b> {month_measurement_unit}</p>
<p><b>Source:</b> {source}</p>
<p><b>KPI Type:</b> {kpi_type}</p>
<p><b>Parent:</b> {parent}</p>
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
    def format_time_series(response, year):
        if not response:
            return "<p>Data not available</p>"

        ts = response.get("time_series")
        if not ts:
            value = response.get("value")
            if value:
                return f"<p>{year}: {value}</p>"
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
