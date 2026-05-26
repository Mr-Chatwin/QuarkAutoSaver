import requests
import re
from typing import List, Dict
from app.core.config import settings

class PanSouClient:
    def __init__(self):
        self.server = settings.PANSOU_API_URL
        self.session = requests.Session()

    def search(self, keyword: str, refresh: bool = False) -> List[Dict]:
        """
        Search for resources using PanSou API
        """
        try:
            url = f"{self.server.rstrip('/')}/api/search"
            params = {
                "kw": keyword,
                "cloud_types": ["quark"],
                "res": "merge",
                "refresh": refresh
            }
            response = self.session.get(url, params=params, timeout=10)
            result = response.json()
            if result.get("code") == 0:
                data = result.get("data", {}).get("merged_by_type", {}).get("quark", [])
                return self.format_search_results(data)
            return []
        except Exception as e:
            print(f"Error searching PanSou: {e}")
            return []

    def format_search_results(self, search_results: list) -> List[Dict]:
        """
        Format PanSou search results into standard dicts
        """
        format_results = []
        link_array = []
        for item in search_results:
            url = item.get("url", "")
            note = item.get("note", "")
            title = note.split('\n')[0] if '\n' in note else note
            
            if url and url not in link_array:
                link_array.append(url)
                format_results.append({
                    "shareurl": url,
                    "taskname": title,
                    "content": note,
                    "channel": item.get("source", ""),
                })

        return format_results
