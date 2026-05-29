import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib3
import re
import os
from urllib.parse import urlparse

urllib3.disable_warnings()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ---------------------------------------------------
# ONLY THESE 3 PAGES
# ---------------------------------------------------

faculty_pages = [
    "https://chennai.vit.ac.in/academics/schools/sas/mfaculty/",
    "https://chennai.vit.ac.in/academics/schools/sas/pfaculty/",
    "https://chennai.vit.ac.in/academics/schools/sas/cfaculty/"
]

# ---------------------------------------------------
# IMAGE FOLDER
# ---------------------------------------------------

IMAGE_FOLDER = "sas_faculty_images_finalChennai"

os.makedirs(
    IMAGE_FOLDER,
    exist_ok=True
)

# ---------------------------------------------------
# STORAGE
# ---------------------------------------------------

all_data = []

visited_profiles = set()

# ---------------------------------------------------
# SCRAPE
# ---------------------------------------------------

for page_url in faculty_pages:

    print("\n================================")
    print("SCRAPING:", page_url)
    print("================================")

    try:

        html = requests.get(
            page_url,
            headers=HEADERS,
            verify=False,
            timeout=15
        ).text

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        cards = soup.find_all(
            "div",
            class_="member-item"
        )

        print(f"\nFACULTY FOUND: {len(cards)}")

        # -------------------------------------------
        # EACH CARD
        # -------------------------------------------

        for card in cards:

            try:

                data = {
                    "employee_id": "",
                    "name": "",
                    "designation": "",
                    "email": "",
                    "research_area": "",
                    "profile_url": "",
                    "image_url": "",
                    "local_image_path": "",
                    "school_page": page_url,
                    "faculty_page": page_url,
                    "campus": "Chennai"
                }

                # -----------------------------------
                # PROFILE URL
                # -----------------------------------

                a = card.find("a", href=True)

                if a:

                    profile_url = a["href"]

                    if profile_url in visited_profiles:
                        continue

                    visited_profiles.add(
                        profile_url
                    )

                    data["profile_url"] = (
                        profile_url
                    )

                # -----------------------------------
                # IMAGE
                # -----------------------------------

                img = card.find("img")

                if img and img.get("src"):

                    image_url = img["src"]

                    data["image_url"] = image_url

                # -----------------------------------
                # NAME
                # -----------------------------------

                h3 = card.find("h3")

                if h3:

                    data["name"] = (
                        h3.get_text(
                            " ",
                            strip=True
                        )
                    )

                # -----------------------------------
                # DESIGNATION
                # -----------------------------------

                h4 = card.find("h4")

                if h4:

                    data["designation"] = (
                        h4.get_text(
                            " ",
                            strip=True
                        )
                    )

                # -----------------------------------
                # DESCRIPTION
                # -----------------------------------

                p = card.find("p")

                text = ""

                if p:

                    text = p.get_text(
                        " ",
                        strip=True
                    )

                # -----------------------------------
                # EMAIL
                # -----------------------------------

                email_match = re.search(
                    r'[\w\.-]+@[\w\.-]+',
                    text
                )

                if email_match:

                    data["email"] = (
                        email_match.group(0)
                    )

                # -----------------------------------
                # EMPLOYEE ID
                # -----------------------------------

                emp_match = re.search(
                    r'Employee ID\s*(\d+)',
                    text,
                    re.IGNORECASE
                )

                if emp_match:

                    data["employee_id"] = (
                        emp_match.group(1)
                    )

                # -----------------------------------
                # RESEARCH AREA
                # -----------------------------------

                ra_match = re.search(
                    r'Research Area:\s*(.*?)(Employee ID|Salutation|Designation)',
                    text,
                    re.IGNORECASE
                )

                if ra_match:

                    data["research_area"] = (
                        ra_match
                        .group(1)
                        .strip()
                    )

                # -----------------------------------
                # DOWNLOAD IMAGE
                # -----------------------------------

                if data["image_url"]:

                    parsed = urlparse(
                        data["image_url"]
                    )

                    ext = os.path.splitext(
                        parsed.path
                    )[1]

                    if not ext:
                        ext = ".jpg"

                    # employee id preferred
                    if data["employee_id"]:

                        filename = (
                            data["employee_id"]
                            + ext
                        )

                    else:

                        safe_name = re.sub(
                            r'[\\\\/*?:\"<>|]',
                            '',
                            data["name"]
                        )

                        filename = (
                            safe_name
                            + ext
                        )

                    filepath = os.path.join(
                        IMAGE_FOLDER,
                        filename
                    )

                    # save only if not exists
                    if not os.path.exists(filepath):

                        img_data = requests.get(
                            data["image_url"],
                            headers=HEADERS,
                            verify=False,
                            timeout=20
                        ).content

                        with open(filepath, "wb") as f:
                            f.write(img_data)

                    data["local_image_path"] = (
                        filepath
                    )

                # -----------------------------------
                # KEEP ONLY REQUIRED FIELDS
                # -----------------------------------

                final_data = {
                    "employee_id":
                        data["employee_id"],

                    "name":
                        data["name"],

                    "designation":
                        data["designation"],

                    "email":
                        data["email"],

                    "research_area":
                        data["research_area"],

                    "profile_url":
                        data["profile_url"],

                    "image_url":
                        data["image_url"],

                    "local_image_path":
                        data["local_image_path"],

                    "school_page":
                        data["school_page"],

                    "faculty_page":
                        data["faculty_page"],

                    "campus":
                        data["campus"]
                }

                all_data.append(final_data)

                print(
                    final_data["employee_id"],
                    final_data["name"]
                )

                # -----------------------------------
                # LIVE SAVE
                # -----------------------------------

                pd.DataFrame(all_data).to_csv(
                    "sas_faculty_clean_finalChennai.csv",
                    index=False
                )

            except Exception as e:

                print("CARD ERROR:", e)

    except Exception as e:

        print("PAGE ERROR:", e)

# ---------------------------------------------------
# FINAL SAVE
# ---------------------------------------------------

final_df = pd.DataFrame(all_data)

final_df = final_df.drop_duplicates(
    subset=["profile_url"]
)

final_df.to_csv(
    "sas_faculty_FINAL_finalChennai.csv",
    index=False
)

print("\n================================")
print("SCRAPING COMPLETE")
print("================================")

print(f"\nTOTAL FACULTY: {len(final_df)}")