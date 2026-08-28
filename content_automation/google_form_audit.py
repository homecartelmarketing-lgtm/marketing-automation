import os
import json
import datetime
import requests
from pathlib import Path
from typing import Any

GOOGLE_FORM_RESPONSE_URL = os.getenv(
    "GOOGLE_FORM_AUDIT_URL",
    "https://docs.google.com/forms/d/e/1FAIpQLSfjMYNCUqFV4lzHC6wImLcO07qw-7xUe9t7JGfn4WdWmG4cIA/formResponse"
)

# Exact mapped Entry IDs for Audit Log Marketing Content Creation Automation Form
ENTRY_DATE_YEAR = os.getenv("GOOGLE_FORM_ENTRY_DATE_YEAR", "entry.644889818_year")
ENTRY_DATE_MONTH = os.getenv("GOOGLE_FORM_ENTRY_DATE_MONTH", "entry.644889818_month")
ENTRY_DATE_DAY = os.getenv("GOOGLE_FORM_ENTRY_DATE_DAY", "entry.644889818_day")

ENTRY_TIME_HOUR = os.getenv("GOOGLE_FORM_ENTRY_TIME_HOUR", "entry.749570514_hour")
ENTRY_TIME_MINUTE = os.getenv("GOOGLE_FORM_ENTRY_TIME_MINUTE", "entry.749570514_minute")

ENTRY_CONTENT_TYPE = os.getenv("GOOGLE_FORM_ENTRY_CONTENT_TYPE", "entry.504365964")
ENTRY_CONTENT_IDEA = os.getenv("GOOGLE_FORM_ENTRY_CONTENT_IDEA", "entry.890670123")
ENTRY_REQUEST_ID = os.getenv("GOOGLE_FORM_ENTRY_REQUEST_ID", "entry.1860414129")
ENTRY_QWEN_API_KEY = os.getenv("GOOGLE_FORM_ENTRY_QWEN_API_KEY", "entry.139997357")
ENTRY_JSON_OUTPUT = os.getenv("GOOGLE_FORM_ENTRY_JSON_OUTPUT", "entry.925884996")

FIXED_QWEN_API_KEY = "1049340"
FIXED_CONTENT_TYPE = "Stories"
FIXED_CONTENT_IDEA = "Product closeup w/ description"


def submit_qwen_audit_form(log_entry: dict[str, Any]) -> bool:
    """Submit Qwen generation audit details to Google Form using Playwright or HTTP POST."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ts_str = log_entry.get("timestamp")
    if ts_str:
        try:
            now = datetime.datetime.fromisoformat(ts_str)
        except Exception:
            pass

    raw_resp = log_entry.get("raw_response") or log_entry.get("raw_api_response") or {}
    request_id = str(raw_resp.get("request_id") or "").strip()
    json_output_str = json.dumps(log_entry, indent=2, ensure_ascii=False)

    # 1. Try Playwright submission via Brave persistent profile
    brave_exe = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    auth_profile_dir = Path(os.path.expanduser("~")) / "AppData" / "Local" / "Temp" / "brave_form_auth_profile"
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            if os.path.exists(brave_exe) and auth_profile_dir.exists():
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(auth_profile_dir),
                    executable_path=brave_exe,
                    headless=True,
                    args=launch_args
                )
            else:
                state_file = Path("output") / "google_auth_state.json"
                browser = p.chromium.launch(headless=True, args=launch_args)
                if state_file.exists():
                    context = browser.new_context(storage_state=str(state_file))
                else:
                    context = browser.new_context()

            page = context.pages[0] if getattr(context, "pages", None) else context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            url = "https://docs.google.com/forms/d/e/1FAIpQLSfjMYNCUqFV4lzHC6wImLcO07qw-7xUe9t7JGfn4WdWmG4cIA/viewform"
            print(f"[AUDIT] Submitting Google Form response via Brave/Playwright for record {log_entry.get('record_id')}...")
            page.goto(url, wait_until="networkidle", timeout=30000)

            if "signin" in page.url:
                print(f"[WARN] Redirected to Google Sign-in. Run 'python scratch/test_brave_form_upload.py' to authenticate.")
                context.close()
            else:
                # Page 1: Content Type = Stories
                page.click("text=Stories")
                page.click("text=Next")
                page.wait_for_timeout(1000)

                # Page 2: Content Idea = Product closeup w/ description
                page.click("text=Product closeup w/ description")
                page.click("text=Next")
                page.wait_for_timeout(1000)

                # Page 3: Request ID, Qwen API Key, JSON Output, File Uploads
                text_inputs = page.query_selector_all("input[type='text']")
                if len(text_inputs) >= 2:
                    if request_id:
                        text_inputs[0].fill(request_id)
                    text_inputs[1].fill(FIXED_QWEN_API_KEY)

                textarea = page.query_selector("textarea")
                if textarea:
                    textarea.fill(json_output_str)

                # Handle file upload inputs if present on page
                file_inputs = page.query_selector_all("input[type='file']")
                generated_img_path = Path("output/content/product_closeup_with_description.jpg")
                if file_inputs and generated_img_path.exists():
                    try:
                        file_inputs[0].set_input_files(str(generated_img_path.resolve()))
                        print(f"[AUDIT] Uploaded generated output photo: {generated_img_path}")
                    except Exception as upload_err:
                        print(f"[WARN] File upload failed: {upload_err}")

                # Submit form
                page.click("text=Submit")
                page.wait_for_timeout(2000)
                print(f"[AUDIT] Successfully submitted Google Form audit response!")
                context.close()
                return True
    except Exception as pw_err:
        print(f"[INFO] Playwright form submission skipped ({pw_err}), trying HTTP POST...")

    # 2. HTTP POST Submission Fallback
    try:
        payload = {
            ENTRY_DATE_YEAR: str(now.year),
            ENTRY_DATE_MONTH: f"{now.month:02d}",
            ENTRY_DATE_DAY: f"{now.day:02d}",
            ENTRY_TIME_HOUR: f"{now.hour:02d}",
            ENTRY_TIME_MINUTE: f"{now.minute:02d}",
            ENTRY_CONTENT_TYPE: FIXED_CONTENT_TYPE,
            ENTRY_CONTENT_IDEA: FIXED_CONTENT_IDEA,
            ENTRY_REQUEST_ID: request_id,
            ENTRY_QWEN_API_KEY: FIXED_QWEN_API_KEY,
            ENTRY_JSON_OUTPUT: json_output_str,
            "pageHistory": "0,1,2",
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        print(f"[AUDIT] Submitting Google Form audit response via HTTP POST for record {log_entry.get('record_id')}...")
        resp = requests.post(GOOGLE_FORM_RESPONSE_URL, data=payload, headers=headers, timeout=30)
        
        if resp.status_code in (200, 302):
            print(f"[AUDIT] Successfully submitted Google Form audit response (Status {resp.status_code}).")
            return True
        else:
            print(f"[WARN] Google Form submission returned status code {resp.status_code}")
            return False
    except Exception as err:
        print(f"[WARN] Failed to submit Google Form audit response: {err}")
        return False
