import requests
from bs4 import BeautifulSoup
import os

# --------------------------
# Configuration
# --------------------------
url = "https://cl.thapar.edu/view1.php"
ccode = "UCS310"  # course code
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)

# --------------------------
# Step 1: Make POST request
# --------------------------
data = {
    "ccode": ccode
}

response = requests.post(url, data=data, verify=False)
response.raise_for_status()  # check for request errors

# --------------------------
# Step 2: Parse the HTML
# --------------------------
soup = BeautifulSoup(response.text, "html.parser")
table = soup.find("table")
rows = table.find_all("tr")[2:]  # skip header rows

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
        link = link_tag["href"]
        downloads.append({
            "course_code": course_code,
            "course_name": course_name,
            "year": year,
            "semester": semester,
            "exam_type": exam_type,
            "link": link
        })

# --------------------------
# Step 3: Sort files
# --------------------------
# Sort by year -> semester -> exam_type
def sort_key(item):
    semester_order = {"E": 0, "O": 1}  # Example: E=Even, O=Odd
    exam_order = {"EST": 0, "MST": 1, "AUX": 2}
    return (int(item["year"]), semester_order.get(item["semester"], 99), exam_order.get(item["exam_type"], 99))

downloads.sort(key=sort_key)

# --------------------------
# Step 4: Download and rename
# --------------------------
session = requests.Session()  # keep session if required

for idx, file in enumerate(downloads, start=1):
    print(file['link'])
    file_url = f"https://cl.thapar.edu/{file['link']}"  # make absolute URL
    
    filename = f"{idx}_{file['course_code']}_{file['year']}_{file['semester']}_{file['exam_type']}.pdf"
    filepath = os.path.join(download_folder, filename)

    # Download file
    r = session.get(file_url, stream=True, verify=False)
    with open(filepath, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"Downloaded: {filename}")

print("All files downloaded successfully!")
