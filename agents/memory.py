import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
import sqlite3
from datetime import datetime
from models.state import AgentState
from dotenv import load_dotenv


def read_memory(state:AgentState)->dict:

    client = chromadb.PersistentClient(path="./nexus_db")

    collection = client.get_or_create_collection("nexus_knowledge")

    results = collection.query(

        query_texts=[state["original_query"]],

        n_results=3

    )

    if results is not None:

        print(results['documents'][0])

    conn = sqlite3.connect('nexus_memory.db')

    cursor = conn.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS session (

                   id INTEGER PRIMARY KEY AUTOINCREMENT,

                   query TEXT,

                   timestamp TEXT,

                   status TEXT

                   )

"""

    )

    cursor.execute(

        "INSERT INTO session (query , timestamp, status) VALUES(?,?,?)",

        (state["original_query"],datetime.now().isoformat(),"started")

    )

    conn.commit()

    conn.close()



    return {"status": "planning"}





def write_memory(state: AgentState)->dict:

    client = chromadb.PersistentClient(path = "./nexus_db")

    collection = client.get_or_create_collection("nexus_knowledge")

    for i , insight in enumerate(state["insights"]):

        collection.add(

            documents=[insight.claim],

            metadatas=[{

                "query": state["original_query"],

                "confidence": str(insight.confidence),

                "source":", ".join(insight.source)

            }],

            ids=[f"{state['original_query'][:20]}_{i}_{datetime.now().timestamp()}"]

        )



    conn = sqlite3.connect("nexus_memory.db")

    cursor = conn.cursor()



    cursor.execute(

        "UPDATE session SET status = ? WHERE id = ?",

        ("completed",state["original_query"])

    )



    conn.commit()

    conn.close()

    return {"status":"approved"}






if __name__ == "__main__":
    import asyncio

    test_state = {
        "original_query": "What are the long term effects of social media on teenagers?",
        "insights": None,
        "status": "planning"
    }

    async def test():
        # test read
        result = read_memory(test_state)
        print(f"Read result: {result}")

        # test write — need some fake insights
        from models.agent_models import Insights
        test_state["insights"] = [
            Insights(
                claim="Social media causes anxiety in teenagers",
                confidence=0.85,
                source=["https://example.com", "https://example2.com"],
                contradictions=[]
            )
        ]
        result = write_memory(test_state)
        print(f"Write result: {result}")

    asyncio.run(test())