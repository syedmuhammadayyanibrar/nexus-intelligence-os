import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from models.state import AgentState
from dotenv import load_dotenv

load_dotenv()

async def run_rag(state: AgentState) -> dict:
    try:
        client = chromadb.PersistentClient(path="./nexus_db")
        collection = client.get_or_create_collection("nexus_knowledge")

        if collection.count() == 0:
            return {"rag_context": [], "status": state["status"]}

        if not state.get("research_plan"):
            return {"rag_context": [], "status": state["status"]}

        rag_context = []
        for sub_q in state["research_plan"].sub_questions:
            results = collection.query(
                query_texts=[sub_q.title],
                n_results=3
            )
            for doc in results["documents"][0]:
                if doc not in rag_context:
                    rag_context.append(doc)

        print(f"RAG found {len(rag_context)} chunks from knowledge base")
        return {"rag_context": rag_context, "status": state["status"]}

    except Exception as e:
        print(f"RAG error: {str(e)}")
        return {"rag_context": [], "status": state["status"]}