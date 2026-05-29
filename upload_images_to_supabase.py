import os
import glob
from dotenv import load_dotenv
from supabase import create_client, Client

# ==============================================================================
# 1. SETUP
# ==============================================================================
# Install required packages first:
#   pip install supabase python-dotenv
#
# Create a .env file with your Supabase credentials:
#   SUPABASE_URL=https://your-project.supabase.co
#   SUPABASE_KEY=your-anon-or-service-role-key
#
# Create a bucket named "faculty-images" in your Supabase project (Dashboard -> Storage).
# Make sure the bucket is marked as "Public".
# ==============================================================================

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in .env")
    exit(1)

supabase: Client = create_client(url, key)
bucket_name = "VITC fac images"
image_folder = "data/vit_chennai_fac_images"

def upload_images():
    print(f"Starting upload to Supabase bucket: '{bucket_name}'...")
    
    # 1. Check if folder exists
    if not os.path.exists(image_folder):
        print(f"Folder not found: {image_folder}")
        return

    # 2. Grab all images (Assuming .jpg, .png, etc.)
    image_files = glob.glob(os.path.join(image_folder, "*.*"))
    if not image_files:
        print("No images found in the directory.")
        return

    # 3. Upload each file
    success_count = 0
    for file_path in image_files:
        file_name = os.path.basename(file_path)
        
        # Determine content type heuristically
        content_type = "image/jpeg"
        if file_name.lower().endswith(".png"):
            content_type = "image/png"
        elif file_name.lower().endswith(".webp"):
            content_type = "image/webp"

        print(f"Uploading {file_name} ... ", end="")
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            try:
                # Upload to Supabase Storage
                # upsert=True overwrites if it already exists
                res = supabase.storage.from_(bucket_name).upload(
                    file_name, 
                    file_bytes, 
                    file_options={"content-type": content_type, "x-upsert": "true"}
                )
                print("SUCCESS")
                success_count += 1
            except Exception as e:
                # If using postgrest < 1.0, some errors are raised natively
                print(f"FAILED ({e})")
                
    print(f"\nDone! Successfully uploaded {success_count}/{len(image_files)} images.")
    print("\nYou can now generate Public URLs for your DB import using:")
    print(f"   {url}/storage/v1/object/public/{bucket_name}/<filename>")

if __name__ == "__main__":
    upload_images()
