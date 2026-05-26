import requests
from typing import Dict, Optional, List
from app.core.config import settings

class TMDBClient:
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = settings.TMDB_API_URL.rstrip('/')
        self.language = "zh-CN"

    def search_multi(self, query: str, year: Optional[str] = None) -> Optional[Dict]:
        """
        Search for a movie or TV show by name, with optional year filtering and ASCII-locale fallback.
        Returns the best matching standard dict with standard name and year.
        """
        if not self.api_key:
            print("TMDB_API_KEY is not set.")
            return {"title": query, "year": year or "Unknown", "type": "movie", "original_title": query}

        import re
        is_ascii = bool(re.match(r'^[\x00-\x7F]+$', query))

        def do_search(lang: Optional[str]) -> List[Dict]:
            url = f"{self.base_url}/search/multi"
            params = {
                "api_key": self.api_key,
                "query": query,
                "page": 1,
                "include_adult": "false"
            }
            if lang:
                params["language"] = lang

            import time
            max_retries = 3
            retry_delay = 1.5
            response = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    break
                except Exception as e:
                    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                        if e.response.status_code in [400, 401, 403, 404]:
                            print(f"[TMDBClient] Non-retryable HTTP error {e.response.status_code}: {e}")
                            return []
                    print(f"[TMDBClient] Request attempt {attempt} failed: {e}")
                    if attempt == max_retries:
                        return []
                    time.sleep(retry_delay)

            try:
                data = response.json()
                return data.get("results", [])
            except Exception as e:
                print(f"[TMDBClient] Error parsing JSON response: {e}")
                return []

        results = []
        if is_ascii:
            results = do_search(None)  # Omit language for English/global search
            if not results:
                results = do_search(self.language)
        else:
            results = do_search(self.language)

        valid_results = [r for r in results if r.get("media_type") in ["movie", "tv"]]
        if not valid_results:
            return None

        # Filter by year if provided
        best_match = None
        if year:
            for r in valid_results:
                date_str = r.get("release_date") or r.get("first_air_date") or ""
                r_year = date_str.split("-")[0] if date_str else ""
                if r_year == year:
                    best_match = r
                    break

        if not best_match:
            best_match = valid_results[0]

        # Retrieve details in Chinese if it's from an English search
        media_type = best_match.get("media_type")
        tmdb_id = best_match.get("id")
        chinese_details = None

        if tmdb_id and media_type in ["movie", "tv"]:
            url_details = f"{self.base_url}/{media_type}/{tmdb_id}"
            params_details = {
                "api_key": self.api_key,
                "language": self.language
            }
            import time
            max_retries = 3
            retry_delay = 1.5
            response_details = None
            for attempt in range(1, max_retries + 1):
                try:
                    response_details = requests.get(url_details, params=params_details, timeout=10)
                    response_details.raise_for_status()
                    break
                except Exception as e:
                    print(f"[TMDBClient] Details request attempt {attempt} failed: {e}")
                    if attempt == max_retries:
                        break
                    time.sleep(retry_delay)

            if response_details:
                try:
                    chinese_details = response_details.json()
                except Exception as e:
                    print(f"[TMDBClient] Error parsing details JSON: {e}")

        if media_type == "movie":
            title = (chinese_details.get("title") if chinese_details else None) or best_match.get("title")
            original_title = best_match.get("original_title")
            release_date = best_match.get("release_date", "")
            r_year = release_date.split("-")[0] if release_date else ""
            return {
                "title": title,
                "original_title": original_title,
                "year": r_year,
                "type": "movie"
            }
        else:
            title = (chinese_details.get("name") if chinese_details else None) or best_match.get("name")
            original_title = best_match.get("original_name")
            first_air_date = best_match.get("first_air_date", "")
            r_year = first_air_date.split("-")[0] if first_air_date else ""
            return {
                "title": title,
                "original_title": original_title,
                "year": r_year,
                "type": "tv"
            }
