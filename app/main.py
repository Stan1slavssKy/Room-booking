from fastapi import FastAPI
from app.routers import auth, users, rooms, bookings
from contextlib import asynccontextmanager
from app.db import init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
   init_database()
   yield


app = FastAPI(
    lifespan=lifespan,
    title="Room booker",
    description="Simple room booker based on FastAPI.",
    version="0.0.1",
    contact={
        "name": "Stan1slavssKy",
        "url": "https://github.com/Stan1slavssKy",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }
)


app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(bookings.router)
