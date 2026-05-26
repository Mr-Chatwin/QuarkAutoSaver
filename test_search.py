import sys
import os
sys.path.insert(0, '/home/cui/QuarkAutoSaver')
from app.services.tmdb import TMDBClient
from app.services.pansou import PanSouClient

tmdb = TMDBClient()
print("Testing TMDB...")
res = tmdb.search_multi("消失的她")
print("TMDB Result:", res)

pansou = PanSouClient()
print("Testing PanSou...")
if res:
    print("Searching PanSou for:", res['title'])
    p_res = pansou.search(res['title'])
    print("PanSou Result Count:", len(p_res))
    if len(p_res) > 0:
        print("First result:", p_res[0])
else:
    print("Searching PanSou for: 消失的她")
    p_res = pansou.search("消失的她")
    print("PanSou Result Count:", len(p_res))
    if len(p_res) > 0:
        print("First result:", p_res[0])
