from fastapi import FastAPI, Depends, Query, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, time, timedelta, date, timezone
from typing import List, Optional, Any
import math
import os

from . import models, database, crawler, utils
from .database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

if not os.path.exists("app/static"):
    os.makedirs("app/static")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    crawler.start_scheduler()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("app/templates/index.html", "r", encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Frontend not found. Please ensure app/templates/index.html exists."

@app.get("/api/search")
def search_classrooms(
    q: Optional[str] = None,
    current_date: str = Query(..., alias="date", description="YYYY-MM-DD"),
    start_time: str = Query(..., description="HH:MM"),
    end_time: str = Query(..., description="HH:MM"),
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    alt: Optional[float] = 0.0, # User altitude in meters (relative to ground or absolute?)
    db: Session = Depends(get_db)
):
    try:
        query_date = datetime.strptime(current_date, "%Y-%m-%d").date()
        s_time = datetime.strptime(start_time, "%H:%M").time()
        e_time = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date/time format")
    
    # 1. Base query for classrooms
    query = db.query(models.Classroom)
    
    if q and q.strip():
        # Fuzzy search: support multiple keywords separated by space
        keywords = q.strip().split()
        for keyword in keywords:
            pattern = f"%{keyword}%"
            # Each keyword must match either name or building_code (case-insensitive)
            query = query.filter(
                or_(
                    models.Classroom.name.ilike(pattern),
                    models.Classroom.building_code.ilike(pattern)
                )
            )
    else:
        # Default behavior: Filter for common teaching buildings (理教, 文萃, 综教)
        # "Logic: Show classrooms where name contains '理教' OR '文萃' OR '综教'"
        default_keywords = ["理教", "文萃", "综教"]
        default_filters = [models.Classroom.name.contains(k) for k in default_keywords]
        query = query.filter(or_(*default_filters))
    
    classrooms = query.all()
    results = []
    
    for room in classrooms:
        # 2. Check availability
        occupancies = db.query(models.Occupancy).filter(
            models.Occupancy.classroom_id == room.id,
            models.Occupancy.date == query_date
        ).all()
        
        is_free_in_range = True
        timeline = []
        
        # Build timeline & check overlap
        for occ in occupancies:
            timeline.append({
                "period": occ.period_number,
                "start": occ.start_time.strftime("%H:%M"),
                "end": occ.end_time.strftime("%H:%M"),
                "state": occ.state
            })
            
            if occ.state != '空闲':
                # Check overlap: (StartA < EndB) and (EndA > StartB)
                if s_time < occ.end_time and e_time > occ.start_time:
                    is_free_in_range = False
        
        if is_free_in_range:
            # 3. Calculate distance and score
            dist = 0
            score = 0
            # Initialize room_alt and user_alt before loop
            room_alt = utils.get_approx_altitude(room.floor)
            user_alt = alt if alt is not None else 0

            if lat is not None and lon is not None:
                # Use flat distance for building detection (horizontal only)

                flat_dist = utils.haversine_distance(lat, lon, room.latitude, room.longitude)
                
                # Heuristic: 
                # If flat_dist < 80m, assume "Same Building" -> Penalty based on floor difference
                # If flat_dist >= 80m, assume "Different Building" -> Penalty based on target floor (climbing up is hard)
                
                SAME_BUILDING_THRESHOLD = 80.0 # meters
                FLOOR_METERS_PENALTY_FACTOR = 10.0 # 1 meter vertical eq 10 meters horizontal walking (stair penalty)
                
                vert_diff = abs(user_alt - room_alt)

                if flat_dist < SAME_BUILDING_THRESHOLD:
                    # Case 1: Same building (Vertical penalty based on difference)
                    score = flat_dist + (vert_diff * FLOOR_METERS_PENALTY_FACTOR)
                else:
                    # Case 2: Different building (Vertical penalty based on target floor height)
                    # Assuming we enter at ground (0m relative).
                    # Penalty = Walk there + Climb up to room floor.
                    score = flat_dist + (room_alt * FLOOR_METERS_PENALTY_FACTOR)

                # Display Distance logic:
                # Euclidean 3D distance (hypotenuse) is dominated by larger side, hiding vertical diff.
                # Instead, we use "Manhattan 3D" (Flat + Vertical) which better represents "Walking Distance".
                # You walk flat to the stairs, then you walk up.
                dist = flat_dist + vert_diff
            
            results.append({
                "id": room.id,
                "name": room.name,
                "building_code": room.building_code,
                "floor": room.floor,
                "latitude": room.latitude,
                "longitude": room.longitude,
                "timeline": sorted(timeline, key=lambda x: x['period']),
                "distance": dist,
                "score": score
            })

    # Sort by heuristic score if lat/lon provided, else by name
    if lat is not None and lon is not None:
        results.sort(key=lambda x: x['score'])
    else:
        results.sort(key=lambda x: x['name'])
        
    return results

@app.post("/api/trigger_scan")
def trigger_scan(background_tasks: BackgroundTasks):
    # Manually trigger crawl (for testing mostly)
    background_tasks.add_task(crawler.update_classroom_data)
    return {"status": "Scan started in background"}
