"""
Load faculty data from CSV and manage ratings/reviews database.
"""
import csv
import os
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
CSV_FILE = DATA_DIR / "vit_chennai_fac.csv"
IMAGES_DIR = DATA_DIR / "vit_chennai_fac_images"

# Mock reviews storage (in production, use database)
_reviews = defaultdict(lambda: {
    "total": 0,
    "w_count": 0,
    "metrics": {"lecture": [], "da": [], "assign": [], "vibe": []},
    "lore": {"green": [], "red": []}
})

def load_faculty():
    """Load faculty data from CSV."""
    faculty = {}
    generated_id_counter = 100000  # Counter for generating IDs for missing employee_ids
    
    if not CSV_FILE.exists():
        print(f"Warning: CSV file not found at {CSV_FILE}")
        return faculty
    
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            emp_id = None
            
            # Try to get employee_id from CSV
            if row['employee_id'].strip().isdigit():
                emp_id = int(row['employee_id'].strip())
            else:
                # Generate a unique ID for faculty without employee_id
                emp_id = generated_id_counter
                generated_id_counter += 1
            
            if not emp_id:
                continue
            
            # Extract school/department from school_page
            school = ""
            if "cse" in row.get('school_page', '').lower():
                school = "CSE"
            elif "ece" in row.get('school_page', '').lower():
                school = "ECE"
            elif "mech" in row.get('school_page', '').lower():
                school = "MECH"
            elif "ssl" in row.get('school_page', '').lower():
                school = "SSL"
            elif "sbst" in row.get('school_page', '').lower():
                school = "SBST"
            else:
                school = "OTHER"
            
            # Find local image file if exists
            image_file = None
            for ext in ['.jpg', '.jpeg', '.png']:
                local_path = IMAGES_DIR / f"{emp_id}.0{ext}"
                if local_path.exists():
                    image_file = f"/data/images/{emp_id}.0{ext}"
                    break
            
            faculty[emp_id] = {
                "id": emp_id,
                "employee_id": emp_id,
                "name": row['name'].strip(),
                "designation": row['designation'].strip(),
                "department": school,
                "email": row.get('email', '').strip(),
                "research_area": row.get('research_area', '').strip(),
                "campus": row.get('campus', 'Chennai').strip(),
                "profile_url": row.get('profile_url', '').strip(),
                "image_url": image_file or row.get('image_url', ''),
                "avatar": row['name'].strip().split()[0][0] + row['name'].strip().split()[-1][0] if row['name'].strip() else "?"
            }
    
    return faculty

def get_faculty_with_reviews(faculty_data):
    """Augment faculty data with review stats."""
    result = []
    for emp_id, prof in faculty_data.items():
        reviews = _reviews[emp_id]
        
        # Calculate metrics averages
        metrics = {}
        for key in ["lecture", "da", "assign", "vibe"]:
            values = reviews["metrics"].get(key, [])
            metrics[key] = sum(values) / len(values) if values else 0.0
        
        # Calculate W/L percentage
        total = reviews["total"]
        w_pct = (reviews["w_count"] / total * 100) if total > 0 else 0
        
        prof_with_stats = {
            **prof,
            "wPct": round(w_pct),
            "reviews": total,
            "metrics": metrics,
            "lore": {
                "green": list(set(reviews["lore"]["green"])),
                "red": list(set(reviews["lore"]["red"]))
            }
        }
        result.append(prof_with_stats)
    
    return result

def add_review(prof_id, payload):
    """Add a review and update stats."""
    reviews = _reviews[prof_id]
    
    # Update metrics
    for key, val in payload.get("metrics", {}).items():
        if key in reviews["metrics"]:
            reviews["metrics"][key].append(val)
    
    # Update verdict
    if payload.get("verdict") == "w":
        reviews["w_count"] += 1
    
    # Add lore
    for lore in payload.get("lore", []):
        if lore not in reviews["lore"]["green"] and lore not in reviews["lore"]["red"]:
            if any(chip in lore for chip in ["pass", "prep", "deadline", "marks", "redo"]):
                reviews["lore"]["green"].append(lore)
            else:
                reviews["lore"]["red"].append(lore)
    
    reviews["total"] += 1

# Load data on import
FACULTY_DATA = load_faculty()
