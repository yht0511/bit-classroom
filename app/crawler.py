import os
import time
from datetime import datetime, timedelta
import bit_login
from sqlalchemy.orm import Session
from .models import Classroom, Occupancy
from .database import SessionLocal
from .utils import parse_floor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of known building codes to crawl
# User requested dynamic fetching of all buildings, so this list is no longer used for looping
# but we can keep it for reference or remove it. 
# SCAN_BUILDINGS = ["2701-6"] 

def update_classroom_data():
    username = os.getenv("BITUSERNAME")
    password = os.getenv("BITPASSWORD")
    
    if not username or not password:
        logger.error("Missing BITUSERNAME or BITPASSWORD env vars")
        return

    try:
        # Initialize login and classroom object
        login_instance = bit_login.jxzxehall_login()
        session_instance = login_instance.login(username, password).get_session()
        classroom_api = bit_login.jxzxehall.classroom(session_instance)
        
        target_date = datetime.now().strftime("%Y-%m-%d") # Scan for today
        
        db: Session = SessionLocal()
        
        try:
            logger.info(f"Scanning all buildings for date {target_date}")
            try:
                # Fetch all classrooms at once (no building_code arg)
                data = classroom_api.get_occupancy(target_date)
                
                for room_data in data:
                    # 1. Update or create Classroom
                    room_name = room_data.get('name')
                    if not room_name: continue
                    
                    # Extract building code from data
                    b_code = room_data.get('building_code', 'Unknown')
                    
                    coords = room_data.get('coordinates', (0, 0))
                    lat, lon = coords if coords else (0, 0)
                    
                    floor = parse_floor(room_name)
                    
                    classroom = db.query(Classroom).filter(Classroom.name == room_name).first()
                    if not classroom:
                        classroom = Classroom(
                            name=room_name,
                            building_code=b_code, 
                            floor=floor,
                            latitude=lat,
                            longitude=lon
                        )
                        db.add(classroom)
                        db.commit()
                        db.refresh(classroom)
                    else:
                        # Update coords just in case
                        classroom.latitude = lat
                        classroom.longitude = lon
                        # Update building code if it was unknown or changed
                        if classroom.building_code == 'Unknown' and b_code != 'Unknown':
                            classroom.building_code = b_code
                        db.commit()

                    # 2. Update Occupancy
                    status_map = room_data.get('status', {})
                    
                    # Clear old occupancies for this date to avoid duplicates/stale data
                    db.query(Occupancy).filter(
                        Occupancy.classroom_id == classroom.id,
                        Occupancy.date == datetime.strptime(target_date, "%Y-%m-%d").date()
                    ).delete()
                    
                    for period_num, info in status_map.items():
                        start_str = info.get('start')
                        end_str = info.get('end')
                        state = info.get('state', 'Unknown')
                        
                        if start_str and end_str:
                            occ = Occupancy(
                                classroom_id=classroom.id,
                                date=datetime.strptime(target_date, "%Y-%m-%d").date(),
                                period_number=int(period_num),
                                start_time=datetime.strptime(start_str, "%H:%M").time(),
                                end_time=datetime.strptime(end_str, "%H:%M").time(),
                                state=state
                            )
                            db.add(occ)
                    
                    db.commit()
                    
            except Exception as e:
                logger.error(f"Error scanning buildings: {e}")
                db.rollback()
                    
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Crawler critical failure: {e}")

from apscheduler.schedulers.background import BackgroundScheduler

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Run every 5 minutes to keep up to date, or adjust as needed
    # Run immediately on start (using datetime.now() + little delay to ensure scheduler is up)
    scheduler.add_job(update_classroom_data, 'interval', minutes=5, next_run_time=datetime.now())
    scheduler.start()
    logger.info("Crawler scheduler started, initial scan triggered.")
