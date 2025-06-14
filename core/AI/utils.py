from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document

from langdetect import detect, LangDetectException


def build_prompt(context: str, question: str) -> ChatPromptTemplate:
    """
    Build the prompt template used for the chatbot.
    Detects question language and sets instructions accordingly to respond in Amharic or English.
    """

    try:
        lang = detect(question)
    except LangDetectException:
        lang = "en"  # ከማስተካከያ ስህተት ከተነሳ እንግሊዝኛ እንደመልስ አድርጉ

    if lang == "am":
        system_content = f'''
        እርስዎ በኢትዮጵያ ኢኮኖሚ ውስጥ በተለየ ሙያ ያለ ሙሉ እውቀት ያላቸው ባለሙያ ናቸው።
        ስምዎ **MoPD Chat Bot** ነው። ከኢኮኖሚ መሠረት፣ ፅንሰ ሐሳብና በእውነተኛ ህይወት ላይ ተግባራዊ ትርጉሞች ላይ ያለዎትን ጥያቄዎች ሁሉ በአማርኛ ይመልሱ።

        - ጥያቄዎች ከኢኮኖሚ በተለያዩ ከሆኑ እንኳን የኢኮኖሚ ሐሳብ አትጨምሩ።
        - ሀገር ካልተገለጸ ጥያቄው ኢትዮጵያ እንደሚመለከተው ይቀይሩ።
        - ቁልፍ ፎርሙላዎች አትጨምሩ።
        - የተረጋጋ ሰነድ መረጃ ብቻ ዋና ምንጭ እንደሆነ ይጠቀሙ።
        - የመረጃው ተረጋጋ እንደሆነ ወይም እንደማይታረጋ በግልጽ ይገልጹ።
        - ተዛማጅ መረጃ ካልተገኘ እንዲህ ይሁን: "በተሰጠው ሰነድ ውስጥ ተዛማጅ መረጃ ሊገኝ አልቻለም።"
        - በሰነዱ ውስጥ ያልተገኘ መረጃ አትፍጠሩ።

        **የኢትዮጵያ ቀን ማስተካከያ**:
        - EFY እና ግሪጎሪያን ቀን ለመለወጥ 7 ዓመት ያክሉ።

        ## Context:
        {context}

        ## Question:
        {question}

        ## Response:
        እባክዎን መልስዎን በHTML ቅርጸ ቃል እንዲህ ያድርጉ:
        - ርዕሶች ለማድረግ <h3> ይጠቀሙ
        - ጽሑፍ ለማቅረብ <p> ይጠቀሙ
        - ዝርዝሮች ለማሳየት <ul>/<li> ይጠቀሙ
        - ሰንጠረዦች ከ <div class="table-responsive"> በሚቀመጡ <table> ውስጥ ያቀርቡ
        '''
    else:
        system_content = f'''
        You are a highly knowledgeable and professional economics expert specializing in Ethiopia's economic data.
        Your name is **MoPD Chat Bot**. Your task is to answer all questions focusing on economic principles, theories, and real-world applications.

        - If a question is unrelated to economics, answer it without incorporating economic concepts.
        - If a country is not explicitly mentioned, assume the question pertains to Ethiopia.
        - Do not include formula details.
        - Use **only verified document data** as the primary source.
        - Clearly indicate whether the information is **verified** (from the document) or **not verified**.
        - If no relevant information is found, state: "Can't find relevant information in the provided document."
        - Do not generate values not in the document.

        **Ethiopian Calendar Conversion**:
        - EFY to Gregorian: add 7 years.

        ## Context:
        {context}

        ## Question:
        {question}

        ## Response:
        Provide your response in HTML with:
        - <h3> for headings.
        - <p> for text.
        - <ul>/<li> for lists.
        - <table> in <div class="table-responsive"> for tables.
        '''

    return ChatPromptTemplate.from_messages([
        SystemMessage(content=system_content),
        MessagesPlaceholder(variable_name="messages"),
    ])


def process_document(to_be_loaded_doc, text_splitter, vector_store) -> bool:
    """
    Load, split, and add a document to the vector store.
    """
    try:
        print("Loading document:", to_be_loaded_doc.file.path)
        loader = PyMuPDFLoader(to_be_loaded_doc.file.path)
        raw_docs = loader.lazy_load()
        documents = [
            Document(page_content=chunk, metadata=raw_doc.metadata)
            for raw_doc in raw_docs
            for chunk in text_splitter.split_text(raw_doc.page_content)
        ]
        doc_ids = [f"doc-{to_be_loaded_doc.id}-{i}" for i in range(len(documents))]

        vector_store.add_documents(documents=documents, ids=doc_ids)

        to_be_loaded_doc.is_loaded = True
        to_be_loaded_doc.save()
        print("Document processed and added to vector store.")
        return True
    except Exception as e:
        print(f"Error processing document {to_be_loaded_doc.file.path}: {e}")
        return False


def run_chain(prompt, llm, conversation_list, context, question):
    """
    Invoke the llm chain with proper inputs.
    """
    from langchain_core.messages import HumanMessage

    chain_input = {
        "context": context,
        "messages": conversation_list + [HumanMessage(content=question)],
    }
    return (prompt | llm).invoke(chain_input)


def format_docs(docs):
    """
    Format documents into a plain text string joined by double line breaks.
    """
    return "\n\n".join(doc.page_content for doc in docs)
