import math
import re

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def parse_floor(room_name: str) -> int:
    """
    Extracts floor number from room name.
    Examples: '文萃楼F101' -> 1, 'F201' -> 2, '201' -> 2
    """
    match = re.search(r'([Ff]?)(\d{3,4})', room_name)
    if match:
        num_part = match.group(2)
        if len(num_part) == 3:
            return int(num_part[0])
        elif len(num_part) == 4:
            return int(num_part[:2])
    return 1 # Default to 1 if not found

def get_approx_altitude(floor: int) -> float:
    """Returns approximate height in meters for a given floor."""
    return (floor - 1) * 3.5

def calculate_3d_distance(lat1, lon1, alt1, lat2, lon2, alt2):
    """
    Returns rough distance in meters considering height.
    alt1, alt2 are in meters.
    """
    flat_dist = haversine_distance(lat1, lon1, lat2, lon2)
    height_diff = abs(alt1 - alt2)
    return math.sqrt(flat_dist**2 + height_diff**2)
