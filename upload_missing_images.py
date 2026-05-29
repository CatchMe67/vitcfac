import os
import glob
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    exit(1)

supabase: Client = create_client(url, key)
bucket_name = "VITC fac images"
image_folder = r"C:\Users\aditya\Desktop\Project\facReviewWEBSITE\missingFaculty_processed_images"

def upload_images():
    print(f"Starting upload to Supabase bucket: '{bucket_name}'...")
    
    if not os.path.exists(image_folder):
        print(f"Folder not found: {image_folder}")
        return

    image_files = glob.glob(os.path.join(image_folder, "*.*"))
    if not image_files:
        print("No images found in the directory.")
        return

    success_count = 0
    for file_path in image_files:
        file_name = os.path.basename(file_path)
        
        content_type = "image/jpeg"
        if file_name.lower().endswith(".png"):
            content_type = "image/png"
        elif file_name.lower().endswith(".webp"):
            content_type = "image/webp"

        print(f"Uploading {file_name} ... ", end="")
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            try:
                res = supabase.storage.from_(bucket_name).upload(
                    file_name, 
                    file_bytes, 
                    file_options={"content-type": content_type, "x-upsert": "true"}
                )
                print("SUCCESS")
                success_count += 1
            except Exception as e:
                print(f"FAILED ({e})")
                
    print(f"\nDone! Successfully uploaded {success_count}/{len(image_files)} images.")

if __name__ == "__main__":
    upload_images()
