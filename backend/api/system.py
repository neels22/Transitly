from fastapi import APIRouter


router = APIRouter(tags=["system"])


@router.get("/")
def root():
    return {"msg": "Transitly backend. Visit /signup or /login."}


@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "transitly-backend"}


