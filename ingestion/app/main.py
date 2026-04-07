from fastapi import FastAPI

app = FastAPI(title="Ingestion Service")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ingestion"}
