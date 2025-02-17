from AI.doc_init_ai import  retriever, format_docs,  llm, chain
from AI.models import QuestionHistory, ChatInstance
from django.shortcuts import render, HttpResponse
from .serializer import ChatInstanceSerializer, QuestionHistorySerializer
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from langchain_core.messages import AIMessage, HumanMessage , SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

def get_chat_history(instance):
    """
    Fetch all previous messages to build the conversation context.
    """
    # Fetch history asynchronously
    history =  QuestionHistory.objects.filter(instance=instance, response__isnull = False)
    
    # Build conversation history
    conversation_list = []
    for record in history:
        conversation_list.append(HumanMessage(content=record.question))
        conversation_list.append(AIMessage(content=record.response))
    return conversation_list

@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def get_answer(request, chat_id):
    
    try:
        instance = ChatInstance.objects.get(id=chat_id)
    except ChatInstance.DoesNotExist:
        return Response({"result" : "FAILURE", "data" : None, "message" : "Instance doesn't exist!"}, status=status.HTTP_400_BAD_REQUEST)
    

    if request.method == 'POST':
        serializer = QuestionHistorySerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(instance=instance)
            question = serializer.data['question']
            question_id = serializer.data['id']
            question_instance = QuestionHistory.objects.get(id=question_id)
        
            #update the title of the instance
            if(not instance.title):
                msg = QuestionHistory.objects.filter(instance = instance).first()
                instance.title = msg.question
                instance.save()
            
            #delete the instances with no title
            none_instances = ChatInstance.objects.filter(title=None)
            none_instances.delete()

            context_docs = retriever.get_relevant_documents(question)
            formatted_context = format_docs(context_docs)


            # Fetch all previous messages to build the conversation context.
            conversation_list = get_chat_history(instance)
            conversation_list.append(HumanMessage(content=question))

            # Prepare the input for the language model
            chain_input = {
                "context": formatted_context,
                "messages": conversation_list,
            }

            prompt = ChatPromptTemplate.from_messages(
                    [
                        SystemMessage(
                            content=f'''
                            You are a highly knowledgeable and professional economics expert specializing in Ethiopia's economic data. 
                            Your name is **MoPD Chat Bot**. Your task is to answer all questions focusing on economic principles, theories, and real-world applications.
                
                            - If a question is unrelated to economics, answer it without incorporating economic concepts.
                            - If a country is not explicitly mentioned, assume the question pertains to Ethiopia.
                            - Do not include formula details in your responses.
                            - Use **only verified document data** as the primary source for your responses.
                            - Clearly indicate whether the information is **verified** (from the document) or **not verified** (external or uncertain).
                            - If no relevant information is found in the provided documents, state: "Can't find relevant information in the provided document."
                            - **Do not generate or add any data that is not explicitly provided in the document**, even if it is seemingly trivial or inferred (e.g., values like "3" or assumptions based on general knowledge).
                            - If a user greets you (e.g., "hi," "hello," or any similar greeting), respond by introducing yourself, stating that your name is **MoPD Chat Bot**, and listing the available documents loaded into the system.
                
                            **Ethiopian Calendar Conversion**:
                            - Ethiopian calendar years (EFY, EC) can be approximated to Gregorian years by adding 7 years.
                
                            Ensure all responses are returned in **HTML format** with the following structure:
                            - Use `<h3>` for headings.
                            - Use `<p>` for body text.
                            - Use `<ul>` and `<li>` for listing items.
                            - For table-based responses:
                              - Wrap the `<table>` element inside a `<div class="table-responsive">` container.
                              - Use `<table class="table">` for styling.
                              - Include a `<thead>` section for the table header.
                              - Close the `</div>` tag at the end to maintain proper layout.
                
                            **Note**: Only documents loaded into the system are considered verified sources.
                
                            ## Context:
                            {formatted_context}
                
                            ## Question:
                            {question}
                
                            ## Response:
                            Please provide your response using the structure outlined above, ensuring adherence to the specified HTML format. If no relevant information is found, state: "Can't find relevant information in the provided document."
                            '''
                        ),
                        MessagesPlaceholder(variable_name="messages"),
                    ])

            ai_response = (prompt | llm).invoke(chain_input)

            question_instance.response = ai_response.content
            question_instance.save()
            question_serializer = QuestionHistorySerializer(question_instance)

            return Response({"result" : "SUCCESS", "message" : "Answer generated successfully!", "data" : question_serializer.data}, status=status.HTTP_200_OK)
        
        return Response({"result" : "FAILURE", "data" : None, "message" : "No Question Provided!"}, status=status.HTTP_400_BAD_REQUEST)
    


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def chat(request, chat_id):
    chat_instances = ChatInstance.objects.filter(user=request.user)
    global is_new
    seriliazer = ChatInstanceSerializer(chat_instances, many=True)

    if request.method == 'GET':
        return Response(seriliazer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        if chat_id == 0:
            instance = ChatInstance()
            instance.user = request.user
            instance.save()
            is_new = True
        else:
            try:
                instance = ChatInstance.objects.get(id=chat_id)
            except ChatInstance.DoesNotExist:
                return Response({"result" : "FAILURE", "data" : None, "message" : "Page not found!"}, status=status.HTTP_400_BAD_REQUEST)
            
        histories = QuestionHistory.objects.filter(instance = instance)
        histories_serializer = QuestionHistorySerializer(histories, many=True)
        return Response(histories_serializer.data, status=status.HTTP_200_OK)
        
    
    return Response({"result" : "FAILURE", "data" : None, "message" : "Page not found!"}, status=status.HTTP_400_BAD_REQUEST)


    