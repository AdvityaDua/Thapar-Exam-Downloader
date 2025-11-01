import os
import time
import tempfile
import shutil
import zipfile
import requests
import uuid
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

import boto3
from botocore.config import Config

# ======================
# Flask Setup
# ======================
app = Flask(__name__)

# ========== Configuration ==========
CLOUDFLARE_ACCOUNT_ID = "e7e753f788a67f62f79ac1ddb1cb05df"
R2_BUCKET_NAME = "thapar-exam-downloader"

R2_ACCESS_KEY_ID = "404d6154cd7107d02991e19292ac15b9"
R2_SECRET_ACCESS_KEY = "72828589b01f2482c9d02e23faef7bc650f12d4db416123a27b721728bb073d7"
R2_ENDPOINT = f"https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

BASE_URL = "https://cl.thapar.edu"
VIEW_URL = f"{BASE_URL}/view1.php"

# ========== Scraper Function ==========
def fetch_exam_links(subject_code):
    """
    Returns a sorted list of exam metadata dicts with download links
    """
    session = requests.Session()
    response = session.post(VIEW_URL, data={"ccode": subject_code}, verify=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")[2:]  # skip headers

    downloads = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        course_code = cols[0].text.strip()
        course_name = cols[1].text.strip()
        year = cols[2].text.strip()
        semester = cols[3].text.strip()
        exam_type = cols[4].text.strip()
        link_tag = cols[5].find("a")

        if link_tag and link_tag.get("href"):
            downloads.append({
                "course_code": course_code,
                "course_name": course_name,
                "year": year,
                "semester": semester,
                "exam_type": exam_type,
                "link": link_tag["href"]
            })

    # Sort by year → semester → exam_type
    def sort_key(item):
        semester_order = {"E": 0, "O": 1}  # Even, Odd
        exam_order = {"EST": 0, "MST": 1, "AUX": 2}
        return (
            int(item["year"]),
            semester_order.get(item["semester"], 99),
            exam_order.get(item["exam_type"], 99),
        )

    downloads.sort(key=sort_key)
    return downloads

# ========== Download + Zip ==========
def download_and_zip(subject_code):
    exams = fetch_exam_links(subject_code)
    if not exams:
        return {"status": "error", "message": "No exams found for given subject code."}

    temp_dir = tempfile.mkdtemp()

    # create subfolders
    for sf in ["MST", "EST", "Auxiliary"]:
        os.makedirs(os.path.join(temp_dir, sf), exist_ok=True)

    session = requests.Session()

    for idx, file in enumerate(exams, start=1):
        file_url = f"{BASE_URL}/{file['link'].lstrip('/')}"
        exam_type = file["exam_type"].upper()
        if exam_type == "AUX":
            subfolder = "Auxiliary"
        else:
            subfolder = exam_type
        
        subfolder_path = os.path.join(temp_dir, subfolder)
        file_text = "Even Sem" if file['semester'] == 'E' else "Odd Sem"
        filename = f"{file_text} {file['year']}.pdf"
        filepath = os.path.join(subfolder_path, filename)

        r = session.get(file_url, stream=True, verify=False)
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    # zip it
    zip_path = os.path.join(temp_dir, f"{subject_code}_exams.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(".zip"):  # skip self
                    continue
                full = os.path.join(root, file)
                rel = os.path.relpath(full, temp_dir)
                zipf.write(full, rel)

    return {"status": "ok", "zip_path": zip_path, "temp_dir": temp_dir}

# ========== R2 Upload ==========
def upload_zip_to_r2(zip_path, key_name):
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )

    with open(zip_path, "rb") as f:
        s3.put_object(Bucket=R2_BUCKET_NAME, Key=key_name, Body=f)

    presigned = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key_name},
        ExpiresIn=86400,
    )
    return presigned

# ========== Flask Route ==========
@app.route("/download", methods=["POST"])
def download_route():
    data = request.json or {}
    subject_code = data.get("subject_code")
    if not subject_code:
        return jsonify({"status": "error", "message": "subject_code is required"}), 400

    result = download_and_zip(subject_code)
    if result.get("status") != "ok":
        return jsonify(result), 500

    zip_path = result["zip_path"]
    temp_dir = result["temp_dir"]
    key_name = f"{subject_code}_exams_{uuid.uuid4().hex}.zip"

    try:
        url = upload_zip_to_r2(zip_path, key_name)
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"status": "error", "message": f"R2 upload error: {str(e)}"}), 500

    shutil.rmtree(temp_dir, ignore_errors=True)
    return jsonify({"status": "ok", "url": url})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)