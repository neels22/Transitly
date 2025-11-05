from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.system import router as system_router
from api.auth import router as auth_router
from api.users import router as users_router
from api.moves import router as moves_router
from api.checklists import router as checklists_router
from api.agents import router as agents_router


app = FastAPI(title="Transitly Backend (dev with Docker)")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(moves_router)
app.include_router(checklists_router)
app.include_router(agents_router)