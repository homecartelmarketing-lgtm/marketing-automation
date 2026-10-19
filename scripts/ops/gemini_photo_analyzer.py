"""Gemini Photo Auto-Upload + Auto-Analyze Bot - PART 1/3."""
from __future__ import annotations
import argparse
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = ROOT / "tmp" / "gemini-chrome-profile"
OUTPUT_DIR = ROOT / "output" / "gemini"
GEMINI_URL = "https://gemini.google.com/app"
DEFAULT_PROMPT = "Analyze this photo in detail. Describe what you see."

def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Auto-upload photo(s) to Gemini in Chrome and capture the answer.")
    p.add_argument("--photo", default=None, help="Path to a single photo to upload.")
    p.add_argument("--photo-folder", default=None, help="Folder of photos (jpg/png/webp).")
    p.add_argument("--prompt", default=DEFAULT_PROMPT, help="Question sent to Gemini with the photo.")
    p.add_argument("--output", default=None, help="File to save the answer (single-photo mode).")
    p.add_argument("--headless", action="store_true", help="Run Chrome headless (default: headed).")
    p.add_argument("--timeout", type=int, default=180, help="Max seconds to wait for answer per photo.")
    p.add_argument("--new-chat", action="store_true", help="Start fresh chat before each upload.")
    return p.parse_args(argv)

def _collect_photos(args) -> list[Path]:
    if args.photo_folder:
        folder = Path(args.photo_folder)
        if not folder.is_dir():
            raise SystemExit(f"[ERROR] --photo-folder not found: {folder}")
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        photos = sorted(x for x in folder.iterdir() if x.suffix.lower() in exts and x.is_file())
        if not photos:
            raise SystemExit(f"[ERROR] No photos found in {folder}")
        return photos
    if args.photo:
        photo = Path(args.photo)
        if not photo.is_file():
            raise SystemExit(f"[ERROR] --photo not found: {photo}")
        return [photo]
    raise SystemExit("[ERROR] Provide --photo <file> or --photo-folder <dir>. See --help.")

def _save_answer(text: str, photo: Path, out_arg: str | None) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if out_arg:
        out = Path(out_arg)
        if not out.is_absolute():
            out = ROOT / out
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = OUTPUT_DIR / f"gemini_answer_{photo.stem}_{ts}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"Photo: {photo}\nGemini answer:\n\n{text}\n", encoding="utf-8")
    return out
def _wait_for_login(page, timeout_s: int = 300):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        url = page.url or ""
        if "accounts.google.com" in url or "ServiceLogin" in url:
            print("[LOGIN] Please log in to Google ONCE in the opened Chrome window... waiting.")
            time.sleep(5)
            continue
        try:
            if page.locator("rich-textarea, div[contenteditable='true']").first.is_visible(timeout=3000):
                return True
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError("Timed out waiting for Gemini login.")

def _start_new_chat(page):
    for sel in ["button:has-text('New chat')", "a:has-text('New chat')", "button:has-text('New Chat')"]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(1500)
                print("[GEMINI] New chat started.")
                return
        except Exception:
            continue

def _upload_photo(page, photo: Path):
    try:
        fi = page.locator("input[type='file']").first
        if fi.count() > 0:
            fi.set_input_files(str(photo))
            print(f"[UPLOAD] set via file input: {photo.name}")
            page.wait_for_timeout(2500)
            return
    except Exception as e:
        print(f"[UPLOAD] direct input failed ({e}), trying attach button...")
    last_err = None
    for sel in ["button[aria-label*='Add files' i]", "button[aria-label*='Upload' i]", "button[aria-label*='Attach' i]"]:
        try:
            btn = page.locator(sel).first
            if btn.count() == 0:
                continue
            btn.wait_for(state="visible", timeout=5000)
            with page.expect_file_chooser(timeout=10000) as fc:
                btn.click()
                page.wait_for_timeout(800)
                for msel in ["text=Upload files", "text=Upload Files"]:
                    try:
                        m = page.locator(msel).first
                        if m.is_visible(timeout=1500):
                            with page.expect_file_chooser(timeout=10000) as fc2:
                                m.click()
                            fc2.value.set_files(str(photo))
                            print(f"[UPLOAD] via menu: {photo.name}")
                            page.wait_for_timeout(2500)
                            return
                    except Exception:
                        continue
            fc.value.set_files(str(photo))
            print(f"[UPLOAD] via chooser: {photo.name}")
            page.wait_for_timeout(2500)
            return
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Upload button not found. Last error: {last_err}")

def _send_prompt(page, prompt: str):
    box = None
    for sel in ["rich-textarea div[contenteditable='true']", "rich-textarea", "div[contenteditable='true']", "div[role='textbox']"]:
        try:
            cand = page.locator(sel).first
            cand.wait_for(state="visible", timeout=5000)
            box = cand
            break
        except Exception:
            continue
    if box is None:
        raise RuntimeError("Prompt box not found. Is gemini.google.com/app loaded?")
    box.click()
    page.wait_for_timeout(400)
    try:
        box.fill(prompt)
    except Exception:
        page.keyboard.type(prompt, delay=10)
    page.wait_for_timeout(3500)
    page.keyboard.press("Enter")
    print("[GEMINI] Prompt sent, waiting for answer...")

def _read_answer(page, timeout_s: int) -> str:
    sel = "message-content, .model-response-text, .markdown-main-panel"
    page.wait_for_selector(sel, timeout=60_000)
    before, stable, last_text = "", 0, ""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            nodes = page.locator(sel).all()
            texts = [n.inner_text().strip() for n in nodes]
            texts = [t for t in texts if t]
            last_text = texts[-1] if texts else ""
        except Exception:
            pass
        try:
            gen = page.locator("button[aria-label*='Stop' i]").first.is_visible(timeout=1000)
        except Exception:
            gen = False
        if last_text and last_text == before and not gen:
            stable += 1
            if stable >= 3:
                break
        else:
            stable = 0
        before = last_text
        time.sleep(2)
    if not last_text:
        raise TimeoutError("No answer captured from Gemini.")
    return last_text

def analyze_photos(photos, prompt, timeout, headless, new_chat, out_arg):
    from playwright.sync_api import sync_playwright
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch_persistent_context(str(PROFILE_DIR), channel="chrome", headless=headless, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1366, "height": 900})
        except Exception as e:
            print(f"[BROWSER] chrome channel missing ({e}); using bundled Chromium.")
            browser = pw.chromium.launch_persistent_context(str(PROFILE_DIR), headless=headless, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1366, "height": 900})
        page = browser.pages[0] if browser.pages else browser.new_page()
        print(f"[BROWSER] Opening {GEMINI_URL} ...")
        page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(3000)
        _wait_for_login(page)
        for i, photo in enumerate(photos, 1):
            print(f"\n===== [{i}/{len(photos)}] {photo.name} =====")
            if new_chat:
                _start_new_chat(page)
            _upload_photo(page, photo)
            _send_prompt(page, prompt)
            answer = _read_answer(page, timeout)
            print(f"[ANSWER] ({len(answer)} chars)\n{answer[:2000]}")
            out_path = _save_answer(answer, photo, out_arg if len(photos) == 1 else None)
            print(f"[SAVED] {out_path}")
            results.append((photo, answer, out_path))
        browser.close()
    return results

def main(argv=None) -> int:
    args = _parse_args(argv)
    photos = _collect_photos(args)
    print(f"[GEMINI-BOT] {len(photos)} photo(s) | prompt: {args.prompt[:80]}")
    analyze_photos(photos, args.prompt, args.timeout, args.headless, args.new_chat, args.output)
    print("\n[DONE] Answers saved under output/gemini/ (or --output).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

