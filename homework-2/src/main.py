from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.api.routers import auth, products, orders, promo_codes
from src.core.logging_middleware import LoggingMiddleware

app = FastAPI(
    title="Marketplace API",
    description="API для управления маркетплейсом",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(LoggingMiddleware)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field_path,
            "message": error["msg"]
        })
    
    return JSONResponse(
        status_code=400,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Ошибка валидации входных данных",
            "details": errors
        }
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Роутеры
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(products.router, prefix="/api/v1", tags=["Products"])
app.include_router(orders.router, prefix="/api/v1", tags=["Orders"])
app.include_router(promo_codes.router, prefix="/api/v1", tags=["PromoCodes"])