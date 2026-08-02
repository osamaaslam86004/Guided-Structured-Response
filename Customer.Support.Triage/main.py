from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from engine import ProductionEngine, get_engine
from schemas import SupportTicketAnalysis

app = FastAPI(title="Outlines Production API")

class TicketRequest(BaseModel):
    ticket_text: str

@app.post("/analyze-ticket", response_model=SupportTicketAnalysis)
def analyze_ticket(
    payload: TicketRequest, 
    engine: ProductionEngine = Depends(get_engine)
):
    try:
        result = engine.analyze(payload.ticket_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))