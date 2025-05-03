from sqlalchemy import Column, Integer, String
from app.db import Base

class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    location = Column(String, nullable=True)
