from fastapi import FastAPI

app = FastAPI(title="MediaDoc")


@app.get("/api/health")
def health():
    return {"status": "ok"}
