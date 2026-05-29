import os
import csv
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    exit(1)

supabase: Client = create_client(url, key)

def import_courses():
    csv_path = "data/courses.csv"
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print("Importing courses...")
    courses = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            credits_val = None
            if row.get('credits'):
                try:
                    credits_val = float(row['credits'])
                except ValueError:
                    pass
                    
            courses.append({
                "course_id": row['course_id'],
                "course_name": row['course_name'],
                "course_type": row.get('type'),
                "credits": credits_val
            })

    batch_size = 100
    for i in range(0, len(courses), batch_size):
        batch = courses[i:i + batch_size]
        supabase.table("courses").upsert(batch).execute()
    print(f"Imported {len(courses)} courses.")


def import_faculty():
    csv_path = "data/vit_chennai_fac.csv"
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print("Importing faculty...")
    faculty = []
    generated_id_counter = 100000
    
    bucket_url_prefix = f"{url}/storage/v1/object/public/VITC fac images/"

    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # normalize headers
        reader.fieldnames = [h.strip() for h in reader.fieldnames]

        for row in reader:
            emp_id_str = row.get('employee_id', '').strip()
            
            if emp_id_str.isdigit():
                emp_id = emp_id_str
            else:
                emp_id = str(generated_id_counter)
                generated_id_counter += 1

            # Determine image URL based on local files existence
            local_jpg = f"data/vit_chennai_fac_images/{emp_id}.0.jpg"
            local_png = f"data/vit_chennai_fac_images/{emp_id}.0.png"
            image_url = None
            if os.path.exists(local_jpg):
                image_url = bucket_url_prefix + f"{emp_id}.0.jpg"
            elif os.path.exists(local_png):
                image_url = bucket_url_prefix + f"{emp_id}.0.png"
            else:
                # fallback to whatever is in the CSV if exists
                image_url = row.get('image_url', '').strip() or None

            # Only add fields that actually exist in your new schema
            faculty.append({
                "employee_id": emp_id,
                "name": row.get('name', '').strip(),
                "designation": row.get('designation', '').strip() or None,
                "email": row.get('email', '').strip() or None,
                "research_area": row.get('research_area', '').strip() or None,
                "profile_url": row.get('profile_url', '').strip() or None,
                "image_url": image_url,
                "school_page": row.get('school_page', '').strip() or None,
                "faculty_page": row.get('faculty_page', '').strip() or None,
                "campus": row.get('campus', 'Chennai').strip() or None,
            })

    batch_size = 100
    for i in range(0, len(faculty), batch_size):
        batch = faculty[i:i + batch_size]
        # using on_conflict='employee_id' in case we rerun it
        supabase.table("faculty").upsert(batch, on_conflict='employee_id').execute()
    print(f"Imported {len(faculty)} faculty records.")

if __name__ == "__main__":
    import_courses()
    import_faculty()
