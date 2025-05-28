from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from api.src.chatbot import get_fact_check_response
from api.src.data_collect import data_collect
from api.src.build_index import build_index
from dotenv import load_dotenv
import os

load_dotenv()

token_header = os.getenv("API_TOKEN_HEADER", "x-api-token")

# ---- FastAPI App Setup ----
app = FastAPI()

# ---- CORS (for dev: allow all origins) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Pydantic Models ----
class QueryRequest(BaseModel):
    query: str
    source_threshold: float

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    scores: list[float]

# ---- Endpoint ----
@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    try:
        result = get_fact_check_response(request.query, threshold=request.source_threshold)

        return QueryResponse(
            answer=result["answer"],
            sources=[f"{src['title']} ({src['url']})" for src in result["sources"]],
            scores=result["scores"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/update-data")
def update_data(request: Request):
    # incoming_token = request.headers.get(token_header)
    # print("Incoming token")
    # print(incoming_token)
    # if incoming_token != os.getenv("API_TOKEN"):
    #     raise HTTPException(status_code=403, detail="Forbidden: Invalid token")
    
    try:
        data_collect()
        return {"status": "success", "message": "Data collection completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data collection failed: {e}")
    
@app.post("/reindex")
def reindex(request: Request):
    # incoming_token = request.headers.get(token_header)
    # print("Incoming token")
    # print(incoming_token)
    # if incoming_token != os.getenv("API_TOKEN"):
    #     raise HTTPException(status_code=403, detail="Forbidden: Invalid token")
    
    try:
        build_index()
        return {"status": "success", "message": "Reindexing completed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindexing failed: {e}")