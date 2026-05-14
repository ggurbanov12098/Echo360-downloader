import sys
import re
from pathlib import Path
import concurrent.futures
from playwright.sync_api import sync_playwright
import traceback

# Import the core logic from src directory
from src.downloader import main as download_main
from src.merger import main as merge_main

def capture_m3u8_links(url: str, safe_title: str) -> dict:
    m3u8_links = {}
    with sync_playwright() as p:
        print(f"[{safe_title}] Launching headless browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def handle_request(request):
            if ".m3u8" in request.url:
                if "s0q1" in request.url and "s0q1" not in m3u8_links:
                    m3u8_links["s0q1"] = request.url
                elif "s1q1" in request.url and "s1q1" not in m3u8_links:
                    m3u8_links["s1q1"] = request.url
                elif "s2q1" in request.url and "s2q1" not in m3u8_links:
                    m3u8_links["s2q1"] = request.url

        page.on("request", handle_request)
        
        try:
            page.goto(url, wait_until="networkidle")
        except Exception:
            print(f"[{safe_title}] Timeout or error navigating, continuing...")
        
        try:
            play_btn = page.get_by_role("button", name="Play", exact=True)
            play_btn.wait_for(timeout=10000)
            play_btn.click()
        except Exception:
            try:
                page.mouse.click(500, 500)
            except Exception:
                pass
        
        page.wait_for_timeout(8000)
        
        if len(m3u8_links) < 3:
            try:
                page.mouse.click(500, 500)
                page.wait_for_timeout(5000)
            except Exception:
                pass

        browser.close()
    return m3u8_links

def process_item(title: str, url: str) -> bool:
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    if not safe_title:
        safe_title = url.split("/")[-2] if "media/" in url else "Echo360_download"
    
    target_dir = Path.cwd() / "downloads" / safe_title
    target_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[{safe_title}] Starting processing for URL: {url}")
    links = capture_m3u8_links(url, safe_title)
    
    if not links:
        print(f"[{safe_title}] Failed to find m3u8 links. Skip or check auth.")
        return False
        
    print(f"[{safe_title}] Captured {len(links)} m3u8 stream links.")
        
    urls_file = target_dir / "urls.txt"
    with urls_file.open("w", encoding="utf-8") as f:
        f.write(f"# Source: {url}\n\n")
        for stream_url in links.values():
            f.write(stream_url + "\n")
            
    try:
        print(f"[{safe_title}] Downloading chunks...")
        dl_code = download_main(target_dir)
        if dl_code != 0:
            print(f"[{safe_title}] Download script returned error code {dl_code}")
            return False
            
        print(f"[{safe_title}] Merging audio/video...")
        merge_code = merge_main(target_dir)
        if merge_code == 0:
            print(f"[{safe_title}] ✅ Done! Saved to 'downloads/{safe_title}'")
            return True
        else:
            print(f"[{safe_title}] Merge failed code {merge_code}")
            return False
    except Exception as e:
        print(f"[{safe_title}] Error during processing: {e}")
        traceback.print_exc()
        return False

def interactive_prompt():
    print("--- Echo360 Downloader ---")
    print("1. Download Single Lecture")
    print("2. Download Bulk Lectures (Parallel)")
    print("--------------------------")
    choice = input("Select an option (1/2): ").strip()
    
    if choice == "1":
        print("\n--- Single Download ---")
        url = input("Enter Echo360 public link: ").strip()
        if not url:
            print("No URL provided.")
            return
        
        title = input("Enter a folder/name for this lecture (optional): ").strip()
        if not title:
            title = "Single_Lecture"
            
        process_item(title, url)

    elif choice == "2":
        print("\n--- Bulk Download ---")
        print("Paste your list containing names and links.")
        print("Example:\nLecture 19 Sequence Models: https://echo360.org/...\n")
        print("When you are done pasting, press Enter on an empty line TWICE to start.")
        
        lines = []
        empty_count = 0
        while True:
            try:
                line = input()
                if not line.strip():
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0
                    lines.append(line)
            except EOFError:
                break
                
        items_to_process = []
        for line in lines:
            match = re.search(r'(https?://[^\s]+)', line)
            if match:
                url = match.group(1)
                title = line.replace(url, "").strip()
                title = re.sub(r'[:\-]+$', '', title).strip()
                items_to_process.append((title, url))
                
        if not items_to_process:
            print("No valid URLs found.")
            return

        print(f"\nProcessing {len(items_to_process)} links in parallel...\n")
        
        # Determine workers - limits to 4 to save RAM/CPU and bandwidth
        workers_count = min(len(items_to_process), 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers_count) as pool:
            futures = [pool.submit(process_item, t, u) for t, u in items_to_process]
            for future in concurrent.futures.as_completed(futures):
                future.result()

        print("\n🎉 Bulk download finished! Check the 'downloads/' folder.")
        
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    try:
        interactive_prompt()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)