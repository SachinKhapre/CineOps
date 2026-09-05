from fastapi import FastAPI

app = FastAPI(title="CineOps")


@app.get("/api/health")
def health():
    return {"status": "ok"}
