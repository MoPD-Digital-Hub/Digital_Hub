from celery import shared_task
from AI.utils import run_chain_stream
from asgiref.sync import async_to_sync, sync_to_async
from AI.models import QuestionHistory, ChatInstance
from AI.ai_instance import retriever, llm
import asyncio
import httpx

@shared_task
def handle_question_task(prompt, conversation_list, full_context, question, chat_id, question_instance_id):

    async def async_worker():
        full_response = ""

        async with httpx.AsyncClient() as client:
            async for chunk in run_chain_stream(
                prompt=prompt,
                llm=llm,
                conversation_list=conversation_list,
                context=full_context,
                question=question
            ):
                full_response += chunk

                await client.post(
                    "http://localhost:9000/stream_chunk",
                    json={"chat_id": chat_id, "chunk": chunk}
                )

        qi = await sync_to_async(QuestionHistory.objects.get)(id=question_instance_id)
        qi.response = full_response
        await sync_to_async(qi.save)()

    asyncio.run(async_worker())
