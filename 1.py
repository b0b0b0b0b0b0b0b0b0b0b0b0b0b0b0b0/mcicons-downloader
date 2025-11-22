import json
import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urljoin
import asyncio
import aiofiles

IDS_FILE = "ids.json"
OUTPUT_DIR = "output"
RESULT_FILE = "result.json"
BASE_URL = "https://mcicons.ccleaf.com"

options = Options()
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(IDS_FILE, 'r', encoding='utf-8') as f:
    ids = json.load(f)

results = {}
id_set = set(ids)

async def save_result_async():
    while True:
        await asyncio.sleep(2)
        if results:
            temp_file = RESULT_FILE + ".tmp"
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(results, indent=2, ensure_ascii=False))
            if os.path.exists(RESULT_FILE):
                os.replace(temp_file, RESULT_FILE)
            else:
                os.rename(temp_file, RESULT_FILE)

def clean_name(name):
    return name.replace(".png", "").strip()

def process_icon(icon):
    alt = icon.get_attribute("alt")
    clean_alt = clean_name(alt).upper().replace(" ", "_")
    if clean_alt not in id_set or clean_alt in results:
        return False
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", icon)
    time.sleep(0.3)
    icon.click()
    time.sleep(1.0)

    modal = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".mc-modal")))
    img_big = modal.find_element(By.CSS_SELECTOR, ".mc-modal-image")
    title = modal.find_element(By.CSS_SELECTOR, ".mc-modal-title").text.strip()
    tags = [t.text.strip() for t in modal.find_elements(By.CSS_SELECTOR, ".mc-tag")]

    main_cat = next((t for t in tags if t in ["Items", "Blocks", "Mobs", "GUI", "Particles", "Weapons", "Paintings"]), "Unknown")
    sub_cat = next((t for t in tags if t not in ["1024x1024", "512x512", main_cat]), "Uncategorized")

    dir_path = os.path.join(OUTPUT_DIR, main_cat, sub_cat)
    os.makedirs(dir_path, exist_ok=True)
    filename = f"{title}.png"
    file_path = os.path.join(dir_path, filename)

    img_url = urljoin(BASE_URL, img_big.get_attribute("src"))
    r = requests.get(img_url, timeout=15)
    if r.status_code == 200:
        with open(file_path, "wb") as f:
            f.write(r.content)

    results[clean_alt] = {
        "name": title,
        "main_category": main_cat,
        "sub_category": sub_cat,
        "file": f"{main_cat}/{sub_cat}/{filename}"
    }

    close_btn = modal.find_element(By.CSS_SELECTOR, ".mc-modal-close")
    close_btn.click()
    time.sleep(0.8)
    return True

def search_and_process_all(item_id):
    global results
    try:
        search_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".mc-search-input input")))
        search_input.clear()
        search_input.send_keys(item_id)
        time.sleep(1.0)

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".mc-icons-grid")))
        time.sleep(1.2)

        icons = driver.find_elements(By.CSS_SELECTOR, ".mc-icon-item img")
        processed_any = False

        for icon in icons:
            if process_icon(icon):
                processed_any = True

        if not processed_any:
            results[item_id] = {"error": "not found"}

    except Exception as e:
        results[item_id] = {"error": str(e)}

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

try:
    driver.get(BASE_URL)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".mc-search-input")))
    time.sleep(2)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, lambda: asyncio.run(save_result_async()))

    for i, item_id in enumerate(ids, 1):
        if item_id in results:
            continue
        print(f"[{i}/{len(ids)}] {item_id}")
        search_and_process_all(item_id)

finally:
    driver.quit()
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)