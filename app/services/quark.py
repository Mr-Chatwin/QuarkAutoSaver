import requests
import re
from typing import Dict, List, Optional
from app.core.config import settings

class QuarkClient:
    def __init__(self):
        self.cookie = settings.QUARK_COOKIE
        self.base_url = "https://drive-h.quark.cn"
        self.headers = {
            "cookie": self.cookie,
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def verify_cookie(self, cookie: str = None) -> bool:
        """Verifies if the cookie is valid by making a test request to Quark Drive"""
        cookie_to_check = cookie if cookie is not None else self.cookie
        url = f"{self.base_url}/1/clouddrive/file/sort?pr=ucpro&fr=pc"
        params = {
            "pdir_fid": "0",
            "_page": "1",
            "_size": "1"
        }
        headers = {
            "cookie": cookie_to_check,
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        try:
            res = requests.get(url, params=params, headers=headers, timeout=10)
            data = res.json()
            return data.get("status") == 200
        except Exception as e:
            print(f"Cookie verification error: {e}")
            return False

    def update_cookie(self, new_cookie: str):
        """Updates the cookie dynamically in headers and session"""
        self.cookie = new_cookie
        self.headers["cookie"] = new_cookie
        self.session.headers.update({"cookie": new_cookie})

    def parse_share_link(self, share_url: str) -> dict:
        """
        Parse share link to get pwd_id and passcode.
        Example: https://pan.quark.cn/s/c1234567890a or https://pan.quark.cn/s/c1234567890a#/list/share
        """
        match = re.search(r'/s/([a-zA-Z0-9]+)', share_url)
        pwd_id = match.group(1) if match else ""
        passcode = "" # Typically none for public shares from PanSou, or embedded in URL
        return {"pwd_id": pwd_id, "passcode": passcode}

    def get_share_token(self, pwd_id: str, passcode: str = "") -> tuple[Optional[str], Optional[str]]:
        url = f"{self.base_url}/1/clouddrive/share/sharepage/token?pr=ucpro&fr=pc"
        payload = {"pwd_id": pwd_id, "passcode": passcode}
        try:
            res = self.session.post(url, json=payload, timeout=10)
            data = res.json()
            if data.get("status") == 200:
                return data.get("data", {}).get("stoken"), None
            else:
                return None, data.get("message", "API response error")
        except Exception as e:
            print(f"Error getting share token: {e}")
            return None, str(e)

    def get_share_list(self, pwd_id: str, stoken: str, pdir_fid: str = "0") -> List[Dict]:
        url = f"{self.base_url}/1/clouddrive/share/sharepage/detail"
        params = {
            "pr": "ucpro",
            "fr": "pc",
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": pdir_fid,
            "_page": "1",
            "_size": "100"
        }
        try:
            res = self.session.get(url, params=params, timeout=10)
            data = res.json()
            if data.get("status") == 200:
                list_data = data.get("data", {}).get("list", [])
                return list_data
        except Exception as e:
            print(f"Error getting share list: {e}")
        return []

    def create_folder(self, parent_id: str, folder_name: str) -> Optional[str]:
        """Creates a folder and returns its fid"""
        url = f"{self.base_url}/1/clouddrive/file?pr=ucpro&fr=pc"
        payload = {
            "file_name": folder_name,
            "pdir_fid": parent_id,
            "scene": "share" # or 'file'
        }
        try:
            res = self.session.post(url, json=payload, timeout=10)
            data = res.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("fid")
        except Exception as e:
            print(f"Error creating folder: {e}")
        return None

    def get_folder_list(self, pdir_fid: str = "0") -> List[Dict]:
        """Get contents of a user's folder"""
        url = f"{self.base_url}/1/clouddrive/file/sort?pr=ucpro&fr=pc"
        params = {
            "pdir_fid": pdir_fid,
            "_page": "1",
            "_size": "100"
        }
        try:
            res = self.session.get(url, params=params, timeout=10)
            data = res.json()
            if data.get("status") == 200:
                return data.get("data", {}).get("list", [])
        except Exception as e:
            print(f"Error getting folder list: {e}")
        return []

    def save_share(self, pwd_id: str, stoken: str, fids: List[str], fid_tokens: List[str], to_pdir_fid: str) -> bool:
        url = f"{self.base_url}/1/clouddrive/share/sharepage/save?pr=ucpro&fr=pc"
        payload = {
            "fid_list": fids,
            "fid_token_list": fid_tokens,
            "to_pdir_fid": to_pdir_fid,
            "pwd_id": pwd_id,
            "stoken": stoken,
            "pdir_fid": "0",
            "scene": "link"
        }
        try:
            res = self.session.post(url, json=payload, timeout=10)
            data = res.json()
            return data.get("code") == 0
        except Exception as e:
            print(f"Error saving share: {e}")
            return False

    def rename_file(self, fid: str, new_name: str) -> bool:
        url = f"{self.base_url}/1/clouddrive/file/rename?pr=ucpro&fr=pc"
        payload = {
            "fid": fid,
            "file_name": new_name
        }
        try:
            res = self.session.post(url, json=payload, timeout=10)
            data = res.json()
            return data.get("code") == 0
        except Exception as e:
            print(f"Error renaming file: {e}")
            return False
