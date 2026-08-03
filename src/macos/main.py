from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
import requests
from customtkinter import *
from PIL import Image
import time
import shutil
import threading
import os
import sys
import glob
import subprocess


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_chromedriver_path():
    """Resolve bundled ChromeDriver path and ensure it is executable."""
    driver_path = resource_path("driver/chromedriver")
    if not os.path.exists(driver_path):
        raise FileNotFoundError(f"ChromeDriver not found at: {driver_path}")

    if not os.access(driver_path, os.X_OK):
        current_mode = os.stat(driver_path).st_mode
        os.chmod(driver_path, current_mode | 0o111)

    return driver_path


def get_chrome_version():
    """Return installed Google Chrome version string, if available."""
    try:
        result = subprocess.run(
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
            capture_output=True,
            text=True,
            check=False
        )
        output = (result.stdout or result.stderr or "").strip()
        if output:
            return output.split()[-1]
    except Exception:
        return None
    return None


def get_driver_version(driver_path):
    """Return chromedriver version string from binary output, if available."""
    try:
        result = subprocess.run([driver_path, "--version"], capture_output=True, text=True, check=False)
        output = (result.stdout or result.stderr or "").strip()
        if output:
            return output.split()[1]
    except Exception:
        return None
    return None


def build_driver_candidates():
    """Collect possible local chromedriver binaries from bundled, cache, and PATH."""
    candidates = []

    try:
        candidates.append(get_chromedriver_path())
    except Exception:
        pass

    cache_globs = [
        os.path.expanduser("~/.wdm/drivers/chromedriver/**/chromedriver"),
        os.path.expanduser("~/.wdm/drivers/chromedriver/**/chromedriver-mac-arm64/chromedriver"),
    ]
    for pattern in cache_globs:
        for path in glob.glob(pattern, recursive=True):
            if os.path.isfile(path):
                candidates.append(path)

    which_driver = shutil.which("chromedriver")
    if which_driver:
        candidates.append(which_driver)

    unique_candidates = []
    seen = set()
    for path in candidates:
        resolved = os.path.realpath(path)
        if resolved not in seen:
            seen.add(resolved)
            unique_candidates.append(path)

    return unique_candidates


def sort_candidates_by_compatibility(candidates):
    """Prefer drivers matching installed Chrome major version."""
    chrome_version = get_chrome_version()
    if not chrome_version:
        return candidates

    chrome_major = chrome_version.split(".")[0]
    matched = []
    unmatched = []

    for path in candidates:
        driver_version = get_driver_version(path)
        if driver_version and driver_version.split(".")[0] == chrome_major:
            matched.append(path)
        else:
            unmatched.append(path)

    return matched + unmatched


def create_chrome_driver(chrome_options):
    """Create Chrome WebDriver with local driver first, then Selenium Manager fallback."""
    setup_errors = []

    candidates = sort_candidates_by_compatibility(build_driver_candidates())

    for candidate in candidates:
        try:
            return webdriver.Chrome(service=Service(candidate), options=chrome_options)
        except Exception as e:
            setup_errors.append(f"Driver failed ({candidate}): {e}")

    try:
        return webdriver.Chrome(options=chrome_options)
    except Exception as e:
        setup_errors.append(f"Auto driver failed: {e}")

    raise RuntimeError(
        "Could not start Chrome. "
        "Your bundled ChromeDriver is likely incompatible with installed Chrome. "
        "Update src/macos/driver/chromedriver to match your Chrome version. "
        + " | ".join(setup_errors)
    )

def check_connection(url='https://www.google.com'):
    """Checks if the internet connection is available using secure SSL verification."""
    try:
        response = requests.get(url, timeout=5)  # Use certifi to verify SSL
        if response.status_code == 200:
            return True
    except requests.RequestException:
        return False


def download_wait(path_to_downloads, timeout=60, check_interval=1):
    """Waits for the download to complete by checking for '.crdownload' files."""
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < timeout:
        time.sleep(check_interval)
        dl_wait = False
        for fname in os.listdir(path_to_downloads):
            if fname.endswith('.crdownload'):
                dl_wait = True
        seconds += check_interval
    if dl_wait:
        print("Warning: Download wait timed out.")
    return seconds
    

def rename_and_move_file(download_path, target_directory, new_name):
    """Renames the most recently downloaded file and moves it to the specified target directory."""
    files = [f for f in os.listdir(download_path) if os.path.isfile(os.path.join(download_path, f))]
    if files:
        latest_file = max([os.path.join(download_path, f) for f in files], key=os.path.getctime)
        file_extension = os.path.splitext(latest_file)[1]
        new_file_path = os.path.join(download_path, new_name + file_extension)
        
        try:
            if not os.access(latest_file, os.W_OK):
                print(f"Cannot access the file {latest_file}. Check file permissions.")
                return
            
            os.rename(latest_file, new_file_path)
            shutil.move(new_file_path, os.path.join(target_directory, os.path.basename(new_file_path)))
            print(f"Renamed and moved {os.path.basename(new_file_path)} to {target_directory}")
        except Exception as e:
            print(f"Error renaming or moving file {latest_file} to {target_directory}: {e}")





class TkinterApp(CTk):
    def __init__(self):
        super().__init__()
        self.title("Thapar Exam Downloader")
        self.minsize(800, 600)
        if sys.platform == 'win32':
            self.iconbitmap(resource_path("icon.ico"))
        
        self.after(100, lambda: self.wm_state("zoomed"))
    
        self.width, self.height = self.winfo_screenwidth(), self.winfo_screenheight()
        self.create_widgets()
        
        
        
    def create_widgets(self):
        self.bg_image = Image.open(resource_path("bg.png"))
        self.bg_photo = CTkImage(self.bg_image, size=(self.winfo_screenwidth(), self.winfo_screenheight()))
        self.bg_label = CTkLabel(self, text="", image=self.bg_photo)
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.logo_image = Image.open(resource_path("logo.png")) # Load your logo image
        
        self.center_frame = CTkFrame(self, fg_color="transparent", width=int(0.3*self.width), height=int(0.6*self.height))
        self.center_frame.place(relx=0.5, rely=0.5, anchor="center")
        self.logo_photo = CTkImage(self.logo_image, size=(100, 100))  # Resize logo (Adjust size as needed)
        self.logo_label = CTkLabel(self.center_frame, text="", image=self.logo_photo)
        self.logo_label.place(relx=0.5, y=10, anchor="n")
        self.head = CTkLabel(self.center_frame, text="Thapar Exam Downloader", font=("Arial", 20, "bold"))
        self.head.place(relx=0.5, rely=0.22, anchor="n")
        
        self.subject_code_label = CTkLabel(self.center_frame, text="Subject Code", font=("Arial", 14))
        self.subject_code_label.place(relx=0.25, rely=0.35, anchor="n")
        self.subject_colan = CTkLabel(self.center_frame, text=":", font=("Arial", 14))
        self.subject_colan.place(relx=0.4, rely=0.35, anchor="n")
        self.subject_entry = CTkEntry(self.center_frame, width=int(0.5*0.3*self.width), placeholder_text="Subject Code")
        self.subject_entry.place(relx=0.45, rely=0.35)
        
        
        self.directory_label = CTkLabel(self.center_frame, text="Download Directory", font=("Arial", 14))
        self.directory_label.place(relx=0.25, rely=0.45, anchor="n")
        self.directory_colan = CTkLabel(self.center_frame, text=":", font=("Arial", 14))
        self.directory_colan.place(relx=0.4, rely=0.45, anchor="n")
        self.directory_entry = CTkEntry(self.center_frame, width=int(0.5*0.3*self.width), placeholder_text="Download Directory")
        self.directory_entry.place(relx=0.45, rely=0.45)

        self.browse_button = CTkButton(self.center_frame, text="Browse", command=self.browse_directory, width=20)
        self.browse_button.place(relx=0.67, rely=0.53, anchor="n")
        
        
        self.download_button = CTkButton(self.center_frame, text="Download", command=self.start_check)
        self.download_button.place(relx=0.5, rely=0.65, anchor="n")
        
        self.label = CTkLabel(self.center_frame, text="", font=("Arial", 14))
        self.label.place(relx=0.5, rely=0.80, anchor="n")
        
        
        self.progress_bar = CTkProgressBar(self.center_frame, width=int(0.5*0.3*self.width))
        self.progress_bar.set(0)
        self.progress_bar.place(relx=0.5, rely=0.9, anchor="n")
        self.progress_bar.place_forget()
    
    def browse_directory(self):
        """Opens a directory selection dialog and updates the entry field."""
        directory = filedialog.askdirectory()
        if directory:
            self.directory_entry.delete(0, 'end')
            self.directory_entry.insert(0, directory)
        
    def check_connection(self):
        if check_connection():
            self.label.configure(text="Internet connection is working.")
            self.update_idletasks()
            try:
                self.download_exam(self.subject_entry.get(), self.directory_entry.get())
            except Exception as e:
                self.progress_bar.place_forget()
                self.label.configure(text=f"Error: {e}")
        else:
            self.label.configure(text="Internet connection is not working. Please check your connection.")
    
    def start_check(self):
        if not self.subject_entry.get():
            self.label.configure(text="Please enter a subject code.")
            return
        if not self.directory_entry.get():
            self.label.configure(text="Please select a download directory.")
            return
        self.label.configure(text="Checking internet connection...")
        threading.Thread(target=self.check_connection, daemon=True).start()
    
    
    def download_exam(self, subject_code, download_path):
        chromeOptions = webdriver.ChromeOptions()
        prefs = {"download.default_directory": download_path}
        chromeOptions.add_experimental_option("prefs", prefs)
        chromeOptions.add_argument("--headless")
        chromeOptions.add_argument("--disable-gpu")  
        chromeOptions.add_argument("--window-size=1920,1080")
        chromeOptions.add_argument("--disable-extensions")  
        chromeOptions.add_argument("--no-sandbox")  
        chromeOptions.add_argument("--disable-dev-shm-usage")  
        
        self.label.configure(text='Please wait while we connect to the server.')
        try:
            driver = create_chrome_driver(chromeOptions)
        except Exception as e:
            self.label.configure(text=f"Chrome setup failed: {e}")
            return

        driver.get("https://cl.thapar.edu/ques.php")
        

        try:
            element_present = EC.presence_of_element_located((By.XPATH, '//*[@id="code"]'))
            WebDriverWait(driver, 10).until(element_present)
            driver.find_element(By.XPATH, value='//*[@id="code"]').send_keys(subject_code)
            
            driver.find_element(By.XPATH, '/html/body/div[3]/div/div[2]/div/div/div/div/table/tbody/tr[1]/td[3]/button').click()
            
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="body"]/table')))
            
            total_exams = len(driver.find_elements(By.XPATH, value='//*[@id="body"]/table/tbody/tr'))

            if total_exams < 3:
                self.label.configure(text="No exams found for the given subject code.")
                self.update_idletasks()
                return
            self.label.configure(text=f'Found {total_exams-2} {"exams." if total_exams-2>1 else "exam."}')
            # **SHOW progress bar when downloading starts**
            self.progress_bar.place(relx=0.5, rely=0.9, anchor="n")
            self.progress_bar.set(0)

            sub_folders = ['MST', 'EST', 'Auxiliary']
            for subfolder in sub_folders:
                subfolder_path = os.path.join(download_path, subfolder)
                os.makedirs(subfolder_path, exist_ok=True)

            for i in range(3, total_exams + 1):
                download_button_xpath = f'//*[@id="body"]/table/tbody/tr[{i}]/td[6]/a'
                driver.find_element(By.XPATH, value=download_button_xpath).click()
                download_wait(download_path)
                selected_subfolder = driver.find_element(By.XPATH, value=f'//*[@id="body"]/table/tbody/tr[{i}]/td[5]').text
                if selected_subfolder.upper() == 'AUX':
                    selected_subfolder = 'Auxiliary'
                specific_directory = os.path.join(download_path, selected_subfolder)

                year = driver.find_element(By.XPATH, value=f'//*[@id="body"]/table/tbody/tr[{i}]/td[3]').text
                semester = driver.find_element(By.XPATH, value=f'//*[@id="body"]/table/tbody/tr[{i}]/td[4]').text

                if semester == 'E':
                    new_name = str('Even Sem ' + year)
                elif semester == 'O':
                    new_name = str('Odd Sem ' + year)

                rename_and_move_file(download_path, specific_directory, new_name)

                # **Update progress bar**
                self.progress_bar.set((i - 2) / (total_exams - 2))
                self.label.configure(text=f"Downloaded exam {i - 2} of {total_exams - 2}")
                self.update_idletasks()

            # **HIDE progress bar after completion**
            self.progress_bar.place_forget()
            self.label.configure(text="Download complete!")

        except TimeoutException:
            print("Page took too long to load.")
        except NoSuchElementException:
            print("Element not found.")
        except WebDriverException:
            print("Web driver error.")
        finally:
            driver.quit()

    
if __name__ == "__main__":
    app = TkinterApp()
    app.mainloop()