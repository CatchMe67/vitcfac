import csv
import os
import re

csv_path = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missing\missingFaculty.csv"
images_dir = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missing\missingFaculty"

images = os.listdir(images_dir)

records = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        records.append(row)

for r in records:
    emp_id = r.get("employee_id", "").strip()
    name = r.get("name", "").strip()
    best_url = r.get("best_image_url", "").strip()
    
    extracted_emp_id = ""
    if not emp_id:
        match = re.search(r'/(\d{5})', best_url)
        if match:
            extracted_emp_id = match.group(1)
            
    final_id = emp_id or extracted_emp_id
    if not final_id:
        print(f"No ID for {name}")

