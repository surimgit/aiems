from fastapi import FastAPI

app = FastAPI(title="Monitoring Service")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "monitoring"}
