import json
import re
import requests
from typing import Optional, Dict
from app.core.config import settings

class LLMClient:
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.api_url = settings.DEEPSEEK_API_URL
        self.model = settings.DEEPSEEK_MODEL

    def parse_media(self, filename: str, parent_folders: list = [], search_keyword: Optional[str] = None) -> Optional[Dict]:
        """
        Uses DeepSeek LLM to extract title, year, season, and episode from filename.
        Returns a dict with keys: 'title', 'year', 'season', 'episode' or None on failure.
        """
        if not self.api_key:
            print("[LLMClient] DEEPSEEK_API_KEY is not set.")
            return None

        url = f"{self.api_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        parent_folder_str = " / ".join(parent_folders) if parent_folders else "None"
        search_kw_str = search_keyword or "None"

        system_prompt = (
            "You are a professional media filename parser.\n"
            "Analyze the given video filename, parent folders, and the user's search keyword to identify the media.\n"
            "Return a JSON object containing the following keys:\n"
            "- 'title': The cleaned, standard Chinese or English title (remove all release groups, codecs, tags, resolutions, and brackets).\n"
            "- 'year': The 4-digit release year as a string (e.g. '2024'), or null if unknown.\n"
            "- 'season': The integer season number (e.g. 1), or null if it's a movie or season is unknown.\n"
            "- 'episode': The integer episode number (e.g. 5), or null if it's a movie or episode is unknown.\n"
            "Respond ONLY with the JSON object. Do not include markdown code block syntax (like ```json ... ```)."
        )

        user_content = (
            f"Filename: {filename}\n"
            f"Parent Folder Path: {parent_folder_str}\n"
            f"User Search Keyword Context: {search_kw_str}"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        try:
            import time
            max_retries = 3
            retry_delay = 1.5
            response = None
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"[LLMClient] Analyzing file: '{filename}' under folder path: '{parent_folder_str}' (attempt {attempt})...")
                    response = requests.post(url, json=payload, headers=headers, timeout=15)
                    response.raise_for_status()
                    break
                except Exception as e:
                    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                        if e.response.status_code in [400, 401, 403, 404]:
                            print(f"[LLMClient] Non-retryable HTTP error {e.response.status_code}: {e}")
                            return None
                    print(f"[LLMClient] Request attempt {attempt} failed: {e}")
                    if attempt == max_retries:
                        return None
                    time.sleep(retry_delay)

            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"].strip()
            
            # Parse response
            data = json.loads(content)
            
            # Normalize fields
            title = data.get("title")
            if not title:
                return None
                
            # Coerce fields to expected types
            year = str(data.get("year")) if data.get("year") else None
            if year and not re.match(r'^\d{4}$', year):
                year = None
                
            season = data.get("season")
            if season is not None:
                try:
                    season = int(season)
                except (ValueError, TypeError):
                    season = None
                    
            episode = data.get("episode")
            if episode is not None:
                try:
                    episode = int(episode)
                except (ValueError, TypeError):
                    episode = None
                    
            res = {
                "title": title.strip(),
                "year": year,
                "season": season,
                "episode": episode
            }
            print(f"[LLMClient] Successfully parsed: {res}")
            return res
        except Exception as e:
            print(f"[LLMClient] Error calling LLM API: {e}")
            return None
