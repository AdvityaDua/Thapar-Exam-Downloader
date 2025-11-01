import os
import time
import tempfile
import shutil
import zipfile
import requests

from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

import boto3
from botocore.config import Config

app = Flask(__name__)

# ========== Configuration ==========

CLOUDFLARE_ACCOUNT_ID = "e7e753f788a67f62f79ac1ddb1cb05df"
R2_BUCKET_NAME = "thapar-exam-downloader"

# These come from your Cloudflare dashboard (keep them secret!)
R2_ACCESS_KEY_ID = "404d6154cd7107d02991e19292ac15b9"
R2_SECRET_ACCESS_KEY = "72828589b01f2482c9d02e23faef7bc650f12d4db416123a27b721728bb073d7"
R2_ENDPOINT = f"https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

# ========== Helper functions ==========

def check_connection(url="https://www.google.com"):
    try:
        resp = requests.get(url, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def download_wait(path_to_downloads, timeout=60, check_interval=1):
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < timeout:
        time.sleep(check_interval)
        dl_wait = False
        for fname in os.listdir(path_to_downloads):
            if fname.endswith(".crdownload"):
                dl_wait = True
        seconds += check_interval
    return seconds

def rename_and_move_file(download_path, target_directory, new_name):
    files = [f for f in os.listdir(download_path) if os.path.isfile(os.path.join(download_path, f))]
    if not files:
        return False, "No files found to rename."
    latest = max([os.path.join(download_path, f) for f in files], key=os.path.getctime)
    ext = os.path.splitext(latest)[1]
    new_full = os.path.join(target_directory, new_name + ext)
    try:
        os.rename(latest, new_full)
        return True, new_full
    except Exception as e:
        return False, str(e)

def download_and_zip(subject_code):
    if not check_connection():
        return {"status": "error", "message": "No internet connection."}

    temp_dir = tempfile.mkdtemp()
    # create subfolders:
    for sf in ["MST", "EST", "Auxiliary"]:
        os.makedirs(os.path.join(temp_dir, sf), exist_ok=True)

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("prefs", {"download.default_directory": temp_dir})

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        driver.get("https://cl.thapar.edu/ques.php")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="code"]')))
        driver.find_element(By.XPATH, '//*[@id="code"]').send_keys(subject_code)
        driver.find_element(By.XPATH, '/html/body/div[3]/div/div[2]/div/div/div/div/table/tbody/tr[1]/td[3]/button').click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="body"]/table')))

        rows = driver.find_elements(By.XPATH, '//*[@id="body"]/table/tbody/tr')
        total_exams = len(rows)
        if total_exams < 3:
            driver.quit()
            shutil.rmtree(temp_dir)
            return {"status": "error", "message": "No exams found for the given subject code."}

        for i in range(3, total_exams + 1):
            download_xpath = f'//*[@id="body"]/table/tbody/tr[{i}]/td[6]/a'
            driver.find_element(By.XPATH, download_xpath).click()
            download_wait(temp_dir)

            subfolder_text = driver.find_element(By.XPATH, f'//*[@id="body"]/table/tbody/tr[{i}]/td[5]').text
            if subfolder_text.upper() == "AUX":
                subfolder_text = "Auxiliary"
            specific_dir = os.path.join(temp_dir, subfolder_text)

            year = driver.find_element(By.XPATH, f'//*[@id="body"]/table/tbody/tr[{i}]/td[3]').text
            semester = driver.find_element(By.XPATH, f'//*[@id="body"]/table/tbody/tr[{i}]/td[4]').text
            new_name = f"{'Even Sem' if semester == 'E' else 'Odd Sem'} {year}"

            rename_and_move_file(temp_dir, specific_dir, new_name)

        zip_path = os.path.join(temp_dir, f"{subject_code}_exams.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == os.path.basename(zip_path):
                        continue
                    full = os.path.join(root, file)
                    rel = os.path.relpath(full, temp_dir)
                    zipf.write(full, rel)

        return {"status": "ok", "zip_path": zip_path, "temp_dir": temp_dir}

    except (TimeoutException, NoSuchElementException, WebDriverException) as e:
        driver.quit()
        shutil.rmtree(temp_dir)
        return {"status": "error", "message": str(e)}
    finally:
        try:
            driver.quit()
        except Exception:
            pass

# ========== R2 Upload ==========

def upload_zip_to_r2(zip_path, key_name):
    """
    Uploads the zip file at zip_path to R2 under key_name using your permanent credentials.
    Returns a presigned URL for download.
    """
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4")
    )

    with open(zip_path, "rb") as f:
        s3.put_object(Bucket=R2_BUCKET_NAME, Key=key_name, Body=f)

    presigned = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key_name},
        ExpiresIn=86400  # 1 day
    )
    return presigned

# ========== Flask route ==========

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
    key_name = f"{subject_code}_exams.zip"

    try:
        url = upload_zip_to_r2(zip_path, key_name)
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"status": "error", "message": f"R2 upload error: {str(e)}"}), 500

    shutil.rmtree(temp_dir, ignore_errors=True)
    return jsonify({"status": "ok", "url": url})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
