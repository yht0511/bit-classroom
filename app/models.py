from sqlalchemy import Column, Integer, String, Float, Date, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Classroom(Base):
    __tablename__ = "classrooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    building_code = Column(String, index=True)
    floor = Column(Integer, default=1)
    latitude = Column(Float)
    longitude = Column(Float)
    
    occupancies = relationship("Occupancy", back_populates="classroom", cascade="all, delete-orphan")

class Occupancy(Base):
    __tablename__ = "occupancies"

    id = Column(Integer, primary_key=True, index=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"))
    date = Column(Date, index=True)
    period_number = Column(Integer)  # 1-13
    start_time = Column(Time)
    end_time = Column(Time)
    state = Column(String)  # '空闲', '排课占用', etc.

    classroom = relationship("Classroom", back_populates="occupancies")

    __table_args__ = (
        UniqueConstraint('classroom_id', 'date', 'period_number', name='_classroom_date_period_uc'),
    )
