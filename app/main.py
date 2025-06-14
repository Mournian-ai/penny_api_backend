# main.py
from fastapi import FastAPI
from app.routes.speak import router as respond_router  # Adjust path if needed
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all your routes here
app.include_router(respond_router)

# Optional: root endpoint
@app.get("/")
def read_root():
    return {"message": "Penny API is running"}
