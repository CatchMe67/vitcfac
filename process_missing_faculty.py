import csv
import os
import re
import shutil

csv_path = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missing\missingFaculty.csv"
images_dir = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missing\missingFaculty"
processed_images_dir = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missingFaculty_processed_images"
out_csv_path = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missingFaculty_ready.csv"

supabase_url = "https://njppucofcctpcurgxunx.supabase.co"
bucket_name = "VITC fac images"

os.makedirs(processed_images_dir, exist_ok=True)
images = os.listdir(images_dir)

out_header = [
    "employee_id", "name", "designation", "school_centre",
    "date_of_joining", "faculty_type", "profile_url",
    "campus", "faculty_image_url"
]

out_records = []

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        emp_id = row.get("employee_id", "").strip()
        name = row.get("name", "").strip()
        best_url = row.get("best_image_url", "").strip()
        
        # Skip Dr. Amit Kumar Rahul (ID: 52318)
        if emp_id == "52318" or "Amit Kumar Rahul" in name:
            continue
            
        extracted_emp_id = ""
        if not emp_id:
            match = re.search(r'/(\d{5})', best_url)
            if match:
                extracted_emp_id = match.group(1)
        
        final_id = emp_id or extracted_emp_id
        if not final_id:
            # Slugify name if still no ID
            final_id = "ID_" + re.sub(r'[^a-zA-Z0-9]', '_', name)
            
        # Find image
        ext = None
        src_image_name = None
        for img in [f"{final_id}.jpg", f"{final_id}.png", f"{name}.jpg", f"{name}.png"]:
            if img in images:
                src_image_name = img
                ext = img.split('.')[-1]
                break
                
        faculty_image_url = ""
        if src_image_name:
            # Copy to processed folder
            dest_image_name = f"{final_id}.{ext}"
            src_path = os.path.join(images_dir, src_image_name)
            dest_path = os.path.join(processed_images_dir, dest_image_name)
            shutil.copy2(src_path, dest_path)
            
            # Construct URL
            faculty_image_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{dest_image_name}"
            
        out_records.append({
            "employee_id": final_id,
            "name": name,
            "designation": row.get("designation", "").strip(),
            "school_centre": row.get("school_centre", "").strip(),
            "date_of_joining": row.get("date_of_joining", "").strip(),
            "faculty_type": row.get("nature_of_association", "").strip(),
            "profile_url": row.get("profile_url", "").strip(),
            "campus": row.get("campus", "").strip(),
            "faculty_image_url": faculty_image_url
        })

with open(out_csv_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=out_header)
    writer.writeheader()
    writer.writerows(out_records)

print(f"Successfully processed {len(out_records)} records.")
print(f"Generated ready CSV at: {out_csv_path}")
