import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.agent_models import Insights
from groq import RateLimitError
import asyncio
from models.state import AgentState
from groq import AsyncGroq
from dotenv import load_dotenv
import json
from pydantic import ValidationError


load_dotenv()
client = AsyncGroq()
async def run_extractor(state:AgentState)->dict:
    all_result = state["search_results"]

    if all_result is None:
        return {
            "status" : "failed",
            "error" : "no search results found"
        }
    
    chunk_size  = 5
    chunk =[all_result[i:i+chunk_size] for i in range (0,len(all_result),chunk_size)]
    async def extract_from_chunk(chunk,sub_question_title):
        formatted = ""
        for i, all_result in enumerate(chunk):
            formatted += f"source {i+1}: {all_result.title}\n"
            formatted += f"Content: {all_result.snippet}\n\n"
        user_message = f"Research topic: {sub_question_title}\n\nSources:\n{formatted}\n\nExtract insights as a JSON array."

        prompt =prompt = """you are a research assistant, return only a valid JSON array.
                            Each insight must follow this exact shape:
                            [
                            {
                                "claim": "a specific factual claim",
                                "confidence": 0.75,
                                "source": ["https://source1.com", "https://source2.com"],
                                "contradictions": []
                            }
                            ]

                            STRICT RULES:
                            - confidence must be a float between 0.0 and 1.0
                            - if confidence is above 0.8, you MUST provide at least 2 source URLs
                            - if you only have 1 source, set confidence to 0.8 or below
                            - source must only contain valid URLs starting with https://
                            - return only the JSON array, no markdown, no explanation
                            """
        i = 0
        while(i<3):
            try:
                response  =await client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                        max_tokens=1000,
                        messages=[
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": user_message}
                        ]
                )
                text = response.choices[0].message.content
                print(f"Extractor raw response:\n{text}\n")
                raw_list = json.loads(text)
                insights = [Insights.model_validate(item) for item in raw_list]
                return insights
            except RateLimitError:
                print("Rate limit hit, waiting 15 seconds...")
                await asyncio.sleep(15)
                continue    

                
            except (ValidationError,json.JSONDecodeError):
                i += 1
                if i >=3 :
                    return{
                        "status":"failed",
                        "error":"validation error"
                    }
                

    tasks = [
        extract_from_chunk(chunk[i], state["research_plan"].sub_questions[i].title)
        for i in range(len(chunk))
    ]


    results = await asyncio.gather(*tasks)
    flattened = [
    insight 
    for sublist in results 
    if isinstance(sublist, list)
    for insight in sublist
    ]
   # print(f"Results from gather: {results}")
   # print(f"Flattened count: {len(flattened)}")
    return {
    "insights": flattened,
    "status": "extracting"
}

    


