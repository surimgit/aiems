from fastapi import FastAPI

app = FastAPI(title="Report Service")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "report"}
