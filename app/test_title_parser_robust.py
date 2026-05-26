import sys
import os
from typing import List, Tuple, Optional

# Add the project root to the python path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.processor import Processor
from app.services.llm import LLMClient

def test_local_parsing():
    print("=== [TEST] 开始测试本地正则与清洗解析 ===")
    p = Processor()

    # 1. 测试 strip_leading_index
    test_cases_index = [
        ("5. 飞驰人生", "飞驰人生"),
        ("02-飞驰人生", "飞驰人生"),
        ("10 飞驰人生", "飞驰人生"),
        ("2019.飞驰人生", "2019.飞驰人生"),  # 年份不应被剥离
        ("飞驰人生", "飞驰人生"),
    ]
    for orig, expected in test_cases_index:
        res = p.strip_leading_index(orig)
        print(f"strip_leading_index('{orig}') => '{res}' (Expected: '{expected}')")
        assert res == expected, f"Failed strip_leading_index for: {orig}"

    # 2. 测试 match_sub_name
    test_cases_sub = [
        ("2.mp4", "飞驰人生3/飞驰人生2/飞驰人生", "飞驰人生2"),
        ("1.mp4", "飞驰人生3/飞驰人生2/飞驰人生", "飞驰人生"),
        ("3.mp4", "飞驰人生3/飞驰人生2/飞驰人生", "飞驰人生3"),
        ("4.mp4", "飞驰人生3/飞驰人生2/飞驰人生", "飞驰人生3/飞驰人生2/飞驰人生 4"), # 找不到匹配，退回原文件夹名+数字
    ]
    for filename, parent_folder, expected in test_cases_sub:
        res = p.match_sub_name(filename.split('.')[0], parent_folder)
        print(f"match_sub_name('{filename}', '{parent_folder}') => '{res}' (Expected: '{expected}')")
        assert res == expected, f"Failed match_sub_name for: {filename}"

    # 3. 测试 parse_title_and_year 各种特殊字符
    test_cases_title = [
        ("飞#驰#人#生", [], "飞驰人生", None),
        ("5. 飞驰人生", [], "飞驰人生", None),
        ("飞 驰 人 生", [], "飞驰人生", None),
        ("飞驰人生 1080p Atmos 60fps 10bit", [], "飞驰人生", None),
        ("飞驰人生.Pegasus.2019.BluRay.x264.mp4", [], "飞驰人生 Pegasus", "2019"),
        ("2.mp4", ["飞驰人生3/飞驰人生2/飞驰人生"], "飞驰人生2", None),
    ]
    for fn, folders, expected_title, expected_year in test_cases_title:
        title, year = p.parse_title_and_year(fn, folders)
        print(f"parse_title_and_year('{fn}', folders={folders}) => Title: '{title}', Year: '{year}' (Expected: '{expected_title}', '{expected_year}')")
        assert title == expected_title, f"Failed title match for: {fn}"
        assert year == expected_year, f"Failed year match for: {fn}"

    # 4. 测试 guess_episode
    test_cases_episode = [
        ("01x.mkv", "E01"),
        ("16x.mkv", "E16"),
        ("21x.mkv", "E21"),
        ("01_v2.mp4", "E01"),
        ("02.mp4", "E02"),
        ("1080p.mp4", ""),
        ("2026.mp4", ""),
    ]
    for fn, expected_ep in test_cases_episode:
        res_ep = p.guess_episode(fn)
        print(f"guess_episode('{fn}') => '{res_ep}' (Expected: '{expected_ep}')")
        assert res_ep == expected_ep, f"Failed guess_episode for: {fn}"

    print("=== [TEST] 本地解析测试全部通过！ ===\n")


def test_llm_parsing():
    print("=== [TEST] 开始测试 DeepSeek 大模型识别 ===")
    client = LLMClient()
    
    if not client.api_key:
        print("⚠️ 警告：未检测到 DEEPSEEK_API_KEY，跳过大模型 API 测试。")
        return

    # 测试用例 1: 复杂合集名称中的子文件
    fn = "2.mp4"
    folders = ["飞驰人生3/飞驰人生2/飞驰人生(三部合集)"]
    search_keyword = "飞驰人生"
    
    print(f"正在向 DeepSeek 请求解析：\n文件名: '{fn}'\n父目录: {folders}\n搜索词: '{search_keyword}'")
    res1 = client.parse_media(fn, folders, search_keyword)
    print(f"DeepSeek 解析结果 1:\n{res1}\n")
    
    assert res1 is not None, "LLM 返回了空对象"
    assert "飞驰人生2" in res1["title"] or "飞驰人生" in res1["title"], f"大模型提取标题不匹配: {res1}"

    # 测试用例 2: 带有多余去噪标签的动漫/电视剧
    fn_tv = "[GM-Team][国漫][凡人修仙传：新年番][A Mortal's Journey to Immortality][2024][101][1080p][HEVC][GB-BIG5][AAC].mp4"
    folders_tv = ["凡人修仙传 新年番"]
    
    print(f"正在向 DeepSeek 请求解析：\n文件名: '{fn_tv}'\n父目录: {folders_tv}")
    res2 = client.parse_media(fn_tv, folders_tv)
    print(f"DeepSeek 解析结果 2:\n{res2}\n")
    
    assert res2 is not None, "LLM 返回了空对象"
    assert "凡人修仙传" in res2["title"], f"大模型未提取出正确的电视剧名: {res2}"
    assert res2["episode"] in [1, 101], f"大模型未正确提取集数: {res2}"
    assert res2["year"] == "2024", f"大模型未正确提取年份: {res2}"

    print("=== [TEST] 大模型解析测试全部通过！ ===")


def test_search_fallback():
    print("=== [TEST] 开始测试搜索降级功能 ===")
    p = Processor()
    # Mock self.tmdb.search_multi to return None to simulate network fail/no match
    p.tmdb.search_multi = lambda query: None
    # Mock pansou.search to return a dummy list to avoid real network call
    p.pansou.search = lambda kw: [{"taskname": f"Mock {kw}", "shareurl": "http://mock"}]
    
    query = "飞#驰#人#生3"
    results = p.process_query(query)
    print(f"process_query('{query}') returned {len(results)} results.")
    
    assert len(results) == 1, "Failed to get mock search results"
    r = results[0]
    print(f"Parsed media_info under TMDB failure: {r['media_info']}")
    assert r['media_info']['title'] == "飞驰人生3", f"Expected title '飞驰人生3', got '{r['media_info']['title']}'"
    assert r['media_info']['year'] == "", "Expected year empty string"
    print("=== [TEST] 搜索降级测试通过！ ===\n")


if __name__ == "__main__":
    test_local_parsing()
    test_llm_parsing()
    test_search_fallback()
