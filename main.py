from fastapi import FastAPI

app = FastAPI(
    title="User Service",
    description="Marketplace microservice - User Domain",
    version="1.0.0"
)

@app.get("/")
def root():
    return {"service": "user-service", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
