from fastapi import FastAPI


app = FastAPI(title="Freight Search")


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}
