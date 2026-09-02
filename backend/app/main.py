from fastapi import FastAPI

app = FastAPI(title="Support Ticketing System API")

@app.get("/health")
def health():
    return {"status": "ok"}