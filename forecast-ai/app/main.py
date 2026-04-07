from fastapi import FastAPI

app = FastAPI(title="Forecast-AI Service")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "forecast-ai"}
