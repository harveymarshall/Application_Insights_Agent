from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI()

class QueryRequest(BaseModel):
    kql_query: str
    app_id: str
    api_key: str

@app.post("/query")
def run_query(request: QueryRequest):
    url = f"https://api.applicationinsights.io/v1/apps/{request.app_id}/query"
    headers = {"x-api-key": request.api_key}
    params = {"query": request.kql_query}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()
