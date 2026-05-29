"""
add_professor.py
────────────────
Utility script to easily upload a professor's image to the Supabase Storage Bucket
and insert/upsert their profile details into the Supabase database.

Usage:
    python add_professor.py <employee_id> <name> <designation> <image_path> [campus]

Example:
    python add_professor.py 52318 "Dr. Amit Kumar Rahul" "Assistant Professor Grade 2" "data/vit_chennai_fac_images/52318.jpg"
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

def main():
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("[-] Error: SUPABASE_URL and SUPABASE_KEY must be set in your .env file.")
        sys.exit(1)

    if len(sys.argv) < 5:
        print("[-] Error: Missing arguments.")
        print("\nUsage:")
        print("    python add_professor.py <employee_id> <name> <designation> <image_path> [campus]")
        print("\nExample:")
        print("    python add_professor.py 52318 \"Dr. Amit Kumar Rahul\" \"Assistant Professor Grade 2\" \"data/vit_chennai_fac_images/52318.jpg\"")
        sys.exit(1)

    emp_id = sys.argv[1].strip()
    name = sys.argv[2].strip()
    designation = sys.argv[3].strip()
    local_image_path = sys.argv[4].strip()
    campus = sys.argv[5].strip() if len(sys.argv) > 5 else "Chennai"

    # 1. Verify local image exists
    if not os.path.exists(local_image_path):
        print(f"[-] Error: Image file not found at '{local_image_path}'")
        sys.exit(1)

    # Get file extension & name
    _, ext = os.path.splitext(local_image_path.lower())
    content_type = "image/jpeg"
    if ext == ".png":
        content_type = "image/png"
    elif ext == ".webp":
        content_type = "image/webp"

    file_name = f"{emp_id}{ext}"
    bucket_name = "VITC fac images"
    
    supabase: Client = create_client(url, key)

    # 2. Upload image to Storage Bucket
    print(f"[*] Uploading '{local_image_path}' to bucket '{bucket_name}' as '{file_name}'...")
    try:
        with open(local_image_path, "rb") as f:
            file_bytes = f.read()

        supabase.storage.from_(bucket_name).upload(
            file_name, 
            file_bytes, 
            file_options={"content-type": content_type, "x-upsert": "true"}
        )
        print("[+] Image upload SUCCESS!")
    except Exception as e:
        print(f"[-] Image upload status (may already exist): {e}")

    # Form the public storage URL
    image_url = f"{url}/storage/v1/object/public/VITC fac images/{file_name}"

    # 3. Upsert into database
    faculty_data = {
        "employee_id": emp_id,
        "name": name,
        "designation": designation,
        "campus": campus,
        "image_url": image_url,
        "email": None,
        "research_area": None,
        "profile_url": None,
        "school_page": None,
        "faculty_page": None
    }

    print(f"[*] Upserting professor details into 'faculty' table: {faculty_data}")
    try:
        res = supabase.table("faculty").upsert(faculty_data, on_conflict="employee_id").execute()
        print("[+] Database upsert SUCCESS!")
        print(f"[+] Record details: {res.data}")
    except Exception as e:
        print(f"[-] Database upsert FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
