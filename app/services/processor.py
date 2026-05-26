import os
import re
from typing import Dict, Optional, List, Callable
from app.services.tmdb import TMDBClient
from app.services.llm import LLMClient
from app.services.pansou import PanSouClient
from app.services.quark import QuarkClient
from app.core.config import settings

class Processor:
    def __init__(self):
        self.tmdb = TMDBClient()
        self.pansou = PanSouClient()
        self.quark = QuarkClient()
        self.llm = LLMClient()
        self.base_folder_id = settings.QUARK_BASE_FOLDER_ID

    def get_or_create_folder_path(self, path: List[str], parent_id: str) -> str:
        """Navigates or creates a folder path, returning the final folder id"""
        current_parent_id = parent_id
        for folder_name in path:
            items = self.quark.get_folder_list(current_parent_id)
            found = False
            for item in items:
                if item.get("file_name") == folder_name and item.get("file_type") == 0: # 0 is folder
                    current_parent_id = item.get("fid")
                    found = True
                    break
            
            if not found:
                new_fid = self.quark.create_folder(current_parent_id, folder_name)
                if not new_fid:
                    raise Exception(f"Failed to create folder: {folder_name}")
                current_parent_id = new_fid
        return current_parent_id

    def parse_season(self, *texts: str, default_to_one: bool = True) -> Optional[int]:
        """Helper to parse season number from given texts, default to 1 if default_to_one is True"""
        cn_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        for text in texts:
            if not text:
                continue
            # Check S02, S2, Season 2
            m1 = re.search(r'(?i)S(\d{1,2})', text)
            if m1:
                return int(m1.group(1))
            m2 = re.search(r'(?i)Season\s*(\d{1,2})', text)
            if m2:
                return int(m2.group(1))
            # Check 第二季, 第2季
            m3 = re.search(r'第\s*([一二三四五六七八九十\d]+)\s*季', text)
            if m3:
                val = m3.group(1)
                if val.isdigit():
                    return int(val)
                return cn_map.get(val, 1)
        return 1 if default_to_one else None


    def guess_episode(self, filename: str) -> str:
        """Extracts EP number, e.g. E01 from various formats"""
        # 0. Check for simple leading episode numbers like 01, 16x, 21x
        name_no_ext = re.sub(r'\.[a-zA-Z0-9]+$', '', filename).strip()
        m_start = re.match(r'^(\d{1,3})(?:[xv\s\-_]|$)', name_no_ext, re.IGNORECASE)
        if m_start:
            num = int(m_start.group(1))
            if num not in [1080, 720, 2160, 480, 576, 60] and not (1900 <= num <= 2100):
                return f"E{num:02d}"

        # 1. Look for S01E05 style
        m1 = re.search(r'(?i)S\d+E(\d{1,3})', filename)
        if m1:
            return f"E{int(m1.group(1)):02d}"
            
        # 2. Look for EP05, E05, 第5集, 第5话
        m2 = re.search(r'(?i)(?:EP|E|第)\s*(\d{1,3})\s*(?:集|话|期|v)?', filename)
        if m2:
            return f"E{int(m2.group(1)):02d}"
            
        # 3. Look for bracketed numbers like [05], 【05】
        m3 = re.search(r'(?:\[|【)\s*(\d{1,3})\s*(?:\]|】)', filename)
        if m3:
            return f"E{int(m3.group(1)):02d}"
            
        # 4. Look for numbers preceded by " - " or spaces, e.g., " - 05"
        m4 = re.search(r'(?:\s-\s|\s+)(\d{1,3})(?:\s+|\.[a-z0-9]+$)', filename, re.IGNORECASE)
        if m4:
            num = int(m4.group(1))
            if num not in [1080, 720, 2160, 480, 576, 60] and not (1900 <= num <= 2100):
                return f"E{num:02d}"
                
        # 5. Look for dot separated numbers, e.g., ".05."
        m5 = re.findall(r'\.(\d{1,3})\.', filename)
        if m5:
            for val in m5:
                num = int(val)
                if num not in [1080, 720, 2160, 480, 576, 60] and not (1900 <= num <= 2100):
                    return f"E{num:02d}"
                    
        return ""

    def process_query(self, query: str) -> List[Dict]:
        """Search step: return list of options"""
        media_info = self.tmdb.search_multi(query)
        if not media_info:
            print(f"[Processor] TMDB search failed or network error for query '{query}'. Falling back to raw query parsing...")
            parsed_title, parsed_year = self.parse_title_and_year(query)
            media_info = {
                "title": parsed_title,
                "year": parsed_year or "",
                "type": "movie"  # Default fallback type
            }
        
        search_kw = f"{media_info['title']}"
        results = self.pansou.search(search_kw)
        
        for r in results:
            r['media_info'] = media_info
            
        return results

    def clean_folder_name(self, folder_name: str) -> str:
        cleaned = re.sub(r'(?i)(?:合集|系列|全集|三部曲|1-\d+部|1-\d+|\b\d+k\b|\b\d{3,4}p\b)', '', folder_name)
        cleaned = re.sub(r'[\[【][^\]】]+[\]】]', '', cleaned)
        cleaned = re.sub(r'[\s\-_\.]+', ' ', cleaned).strip()
        return cleaned

    def is_simple_name(self, filename_no_ext: str) -> bool:
        val = filename_no_ext.strip()
        if len(val) <= 3:
            return True
        if val.isdigit():
            return True
        if re.match(r'(?i)^(?:ep|e|part|pt)?\d+$', val):
            return True
        return False

    def strip_leading_index(self, name: str) -> str:
        """Strips leading list indexes like '5. ', '02-', '10 ' if it doesn't represent a year and doesn't leave the string empty."""
        m = re.match(r'^(\d+)([\.\s\-_、/]+)', name)
        if m:
            num_str = m.group(1)
            # If it looks like a year, don't strip
            if len(num_str) == 4 and 1900 <= int(num_str) <= 2100:
                return name
            rest = name[m.end():].strip()
            if not rest:
                return name
            return rest
        return name

    def match_sub_name(self, simple_name: str, parent_folder: str) -> str:
        """
        Maps a simple filename (like '1', '2', '3') to the corresponding movie in a slash/pipe/comma separated parent folder name.
        E.g. parent_folder='飞驰人生3/飞驰人生2/飞驰人生', simple_name='2' -> returns '飞驰人生2'
        """
        # Split by common delimiters: /, |, 、
        sub_names = [s.strip() for s in re.split(r'[/|、\+]', parent_folder) if s.strip()]
        if len(sub_names) <= 1:
            return f"{parent_folder} {simple_name}"

        # Extract digit from the simple name
        digit_match = re.search(r'\d+', simple_name)
        if digit_match:
            digit = digit_match.group(0)
            
            # 1. Look for exact digit match in sub-names (excluding year)
            for sn in sub_names:
                sn_no_year = re.sub(r'\b(19\d{2}|20\d{2})\b', '', sn)
                # Matches digit as word boundary or next to non-digits
                if re.search(r'\b' + digit + r'\b|\D' + digit + r'\b|\b' + digit + r'\D', sn_no_year):
                    return sn
            
            # 2. If digit is 1, search for a sub-name with no digit (e.g. '飞驰人生' without '1' represents 1st part)
            if int(digit) == 1:
                for sn in sub_names:
                    sn_no_year = re.sub(r'\b(19\d{2}|20\d{2})\b', '', sn)
                    if not re.search(r'\d+', sn_no_year):
                        return sn

        # Fallback: if there is a 1-to-1 matching length, or just return whole folder with simple name
        return f"{parent_folder} {simple_name}"

    def parse_title_and_year(self, filename: str, parent_folders: List[str] = []) -> tuple[str, Optional[str]]:
        # Remove file extension
        name = re.sub(r'\.[a-zA-Z0-9]+$', '', filename).strip()
        
        # Check if simple name and parent folder is available
        if self.is_simple_name(name) and parent_folders:
            cleaned_parent = self.clean_folder_name(parent_folders[-1])
            if cleaned_parent:
                name = self.match_sub_name(name, cleaned_parent)
                
        # Replace comprehensive set of separators/noise characters with spaces
        special_chars = r"[、.。,，·:：;；!！'’\"“”()（）\[\]【】「」\-—―\+\|\\_/&#～~]"
        name = re.sub(special_chars, ' ', name)
        
        # Strip leading indexes (e.g. '5  飞驰人生' -> '飞驰人生')
        name = self.strip_leading_index(name.strip())
        
        # Merge spaces between consecutive Chinese characters (e.g. '飞 驰 人 生' -> '飞驰人生')
        name = re.sub(r'(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])', '', name)
        
        # Try to find a 4-digit year (1900-2100)
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
        year = None
        title = name
        
        if year_match:
            year = year_match.group(1)
            idx = name.find(year)
            title = name[:idx].strip()
        else:
            # truncate title by common video tags (expanded significantly)
            tags = [
                # Resolutions
                r'\b\d{3,4}[pi]\b', r'\b[248]k\b',
                # Video source / Release type
                r'\bbluray\b', r'\bweb[-.]?dl\b', r'\bweb[-.]?rip\b', r'\bremux\b', r'\buhd\b', r'\bbd[-.]?rip\b', r'\bhd[-.]?rip\b', r'\bdvd[-.]?rip\b', r'\bhdtv\b',
                # Video Codec
                r'\bx26[45]\b', r'\bh26[45]\b', r'\bhevc\b', r'\bavc\b', r'\bav1\b',
                # Audio Codec / channels
                r'\bdts[-.]?(hd|ma)?\b', r'\batmos\b', r'\btruehd\b', r'\baac\b', r'\bflac\b', r'\bac3\b', r'\bddp?\d?\b',
                # Video dynamics/fps/color
                r'\bhdr\d*\b', r'\bsdr\b', r'\bdolby\b', r'\bdovi\b', r'\b60fps\b', r'\b10bit\b', r'\b8bit\b', r'\bhq\b',
                # Languages / Subtitles / Dubbing (English)
                r'\bdual[-.]?audio\b', r'\bchs\b', r'\bcht\b', r'\beng?\b',
                # Languages / Subtitles / Dubbing (Chinese)
                r'简体', r'繁体', r'中文字幕', r'中英双字', r'中字', r'双字', r'国粤双语', r'国语', r'粤语', r'双语', r'简繁', r'无水印', r'高码率', r'蓝光原盘', r'蓝光'
            ]
            earliest_idx = len(name)
            for tag in tags:
                match = re.search(tag, name, re.IGNORECASE)
                if match and match.start() < earliest_idx:
                    earliest_idx = match.start()
            if earliest_idx < len(name):
                title = name[:earliest_idx].strip()
                
        title = re.sub(r'\s+', ' ', title).strip()
        return title, year

    def save_and_rename(self, share_url: str, media_info: dict, status_callback: Optional[Callable[[str], None]] = None) -> str:
        """Saves a share link and renames contents to Emby standard using multi-movie/TV auto-splitting"""
        def report(text: str):
            if status_callback:
                try:
                    status_callback(text)
                except Exception as e:
                    print(f"Callback error: {e}")

        report("🔍 正在解析分享链接...")
        share_info = self.quark.parse_share_link(share_url)
        pwd_id = share_info["pwd_id"]
        passcode = share_info["passcode"]
        
        if not pwd_id:
            return "Failed to parse share link."

        stoken, err_msg = self.quark.get_share_token(pwd_id, passcode)
        if not stoken:
            return f"❌ 无法解析分享链接：{err_msg or '未知错误'}"

        report("📁 正在分析分享内容并检索文件树...")
        share_list = self.quark.get_share_list(pwd_id, stoken)
        if not share_list:
            return "Share is empty or expired."

        # Recursively collect all files with parent folder history
        all_files = []
        def collect_files(pdir_fid: str, path_prefix: List[str] = []):
            items = self.quark.get_share_list(pwd_id, stoken, pdir_fid)
            for item in items:
                if item.get("file_type") == 1: # 1 is file
                    item["parent_folders"] = path_prefix
                    all_files.append(item)
                elif item.get("file_type") == 0: # 0 is folder
                    collect_files(item.get("fid"), path_prefix + [item.get("file_name")])
        
        try:
            collect_files("0", [])
        except Exception as e:
            print(f"Error collecting files recursively: {e}")

        if not all_files:
            return "No files found in share link."

        # Separate video files from non-video files
        video_extensions = {'.mp4', '.mkv', '.avi', '.flv', '.rmvb', '.ts', '.mov', '.wmv', '.m4v', '.mpg'}
        video_files = []
        non_video_files = []
        for f in all_files:
            name = f.get("file_name", "")
            ext = os.path.splitext(name)[1].lower() if '.' in name else ""
            if ext in video_extensions:
                video_files.append(f)
            else:
                non_video_files.append(f)

        # Fallback details from search target
        search_title = media_info.get("title")
        search_year = media_info.get("year")
        search_type = media_info.get("type")
        search_emby_title = f"{search_title} ({search_year})" if search_year else search_title
        if search_type == "movie":
            search_path = ["Movies", search_emby_title]
        else:
            folder_names = [item.get("file_name") for item in share_list if item.get("file_type") == 0]
            first_item_name = share_list[0].get("file_name") if share_list else ""
            search_season = self.parse_season(search_title, first_item_name, *folder_names)
            search_path = ["TV", search_emby_title, f"Season {search_season:02d}"]

        # Cache TMDB queries to prevent duplicate requests
        tmdb_cache = {}
        def query_tmdb_cached(title: str, year: Optional[str] = None) -> Optional[dict]:
            if not title:
                return None
            cache_key = (title, year)
            if cache_key in tmdb_cache:
                return tmdb_cache[cache_key]
            res = self.tmdb.search_multi(title, year)
            tmdb_cache[cache_key] = res
            return res

        # Map each video file to its target path and expected Emby name
        groups = {}
        
        report("⚡ 正在执行智能刮削与路径计算...")
        for vf in video_files:
            orig_name = vf.get("file_name")
            parent_folders = vf.get("parent_folders", [])
            ext = orig_name.split('.')[-1] if '.' in orig_name else "mp4"
            
            parsed_title, parsed_year = self.parse_title_and_year(orig_name, parent_folders)
            
            scraped = query_tmdb_cached(parsed_title, parsed_year)
            
            # If TMDB lookup fails, try LLM fallback
            llm_res = None
            if not scraped and settings.DEEPSEEK_API_KEY:
                print(f"[Processor] Local search failed for '{parsed_title}'. Invoking DeepSeek LLM fallback...")
                llm_res = self.llm.parse_media(orig_name, parent_folders, search_title)
                if llm_res and llm_res.get("title"):
                    llm_title = llm_res["title"]
                    llm_year = llm_res.get("year")
                    print(f"[Processor] LLM parsed title: '{llm_title}', year: '{llm_year}'. Retrying TMDB...")
                    scraped = query_tmdb_cached(llm_title, llm_year)
                    if scraped:
                        print(f"[Processor] DeepSeek Fallback Success! Matched: {scraped['title']} ({scraped['year']})")
            
            # Extract canonical title, year, and media type
            if scraped:
                title = scraped.get("title")
                year = scraped.get("year")
                mtype = scraped.get("type")
            elif llm_res and llm_res.get("title"):
                title = llm_res["title"]
                year = llm_res.get("year")
                if llm_res.get("season") is not None or llm_res.get("episode") is not None:
                    mtype = "tv"
                else:
                    mtype = search_type
            else:
                title = search_title
                year = search_year
                mtype = search_type

            emby_title = f"{title} ({year})" if year else title

            # Determine saving path and expected Emby standard name
            if mtype == "movie":
                path = ["Movies", emby_title]
                if len(video_files) > 1 and not scraped and not (llm_res and llm_res.get("title")):
                    file_idx = video_files.index(vf) + 1
                    expected_name = f"{emby_title} - Part {file_idx}.{ext}"
                else:
                    expected_name = f"{emby_title}.{ext}"
            else: # tv
                # Priority: local deterministic rules first
                local_season = self.parse_season(orig_name, *parent_folders, default_to_one=False)
                local_ep = self.guess_episode(orig_name)
                
                local_ep_num = None
                if local_ep:
                    m_ep = re.match(r'^E(\d+)$', local_ep, re.IGNORECASE)
                    if m_ep:
                        local_ep_num = int(m_ep.group(1))

                # Season logic
                if local_season is not None:
                    season_num = local_season
                elif llm_res and llm_res.get("season") is not None:
                    llm_season = llm_res.get("season")
                    # If LLM parsed season matches the episode number parsed locally, it is likely a misidentification
                    if local_ep_num is not None and llm_season == local_ep_num:
                        print(f"[Processor] Safety override: LLM season {llm_season} matches local episode number {local_ep_num}. Discarding LLM season.")
                        season_num = search_season
                    else:
                        season_num = llm_season
                else:
                    season_num = search_season
                
                path = ["TV", emby_title, f"Season {season_num:02d}"]

                # Episode logic
                if local_ep:
                    ep = local_ep
                    vf["ep_num"] = local_ep_num
                elif llm_res and llm_res.get("episode") is not None:
                    llm_ep = llm_res.get("episode")
                    ep = f"E{llm_ep:02d}"
                    vf["ep_num"] = llm_ep
                else:
                    ep = ""
                    vf["ep_num"] = None

                if ep:
                    expected_name = f"{emby_title} - S{season_num:02d}{ep}.{ext}"
                else:
                    if len(video_files) > 1:
                        file_idx = video_files.index(vf) + 1
                        expected_name = f"{emby_title} - Part {file_idx} - {orig_name}"
                    else:
                        expected_name = f"{emby_title} - {orig_name}"

            vf["target_path"] = path
            vf["expected_name"] = expected_name
            vf["mtype"] = mtype
            vf["scraped_emby_title"] = emby_title
            
            path_tuple = tuple(path)
            if path_tuple not in groups:
                groups[path_tuple] = []
            groups[path_tuple].append(vf)

        # Route non-video files (like subtitles) to the closest video file's target path
        for nvf in non_video_files:
            orig_name = nvf.get("file_name")
            ext = orig_name.split('.')[-1] if '.' in orig_name else "srt"
            
            best_match_vf = None
            longest_prefix_len = 0
            for vf in video_files:
                vf_name = vf.get("file_name")
                common_prefix = os.path.commonprefix([orig_name.lower(), vf_name.lower()])
                if len(common_prefix) > longest_prefix_len:
                    longest_prefix_len = len(common_prefix)
                    best_match_vf = vf
                    
            if best_match_vf:
                nvf["target_path"] = best_match_vf["target_path"]
                nvf["mtype"] = best_match_vf["mtype"]
                v_expected = best_match_vf["expected_name"]
                v_base = os.path.splitext(v_expected)[0]
                lang_match = re.search(r'\.(zh|cn|sc|tc|eng?|ch[is])\.[a-zA-Z0-9]+$', orig_name, re.IGNORECASE)
                if lang_match:
                    lang = lang_match.group(1).lower()
                    expected_name = f"{v_base}.{lang}.{ext}"
                else:
                    expected_name = f"{v_base}.{ext}"
            else:
                nvf["target_path"] = search_path
                nvf["mtype"] = search_type
                expected_name = orig_name
                
            nvf["expected_name"] = expected_name
            
            path_tuple = tuple(nvf["target_path"])
            if path_tuple not in groups:
                groups[path_tuple] = []
            groups[path_tuple].append(nvf)

        saved_paths = []
        missing_reports = []
        failed_groups = 0
        total_groups = len(groups)
        
        for idx, (path_tuple, files_list) in enumerate(groups.items()):
            path = list(path_tuple)
            report(f"📂 正在处理目录 [{idx+1}/{total_groups}]: {'/'.join(path)}")
            
            try:
                target_folder_id = self.get_or_create_folder_path(path, self.base_folder_id)
            except Exception as e:
                print(f"Error creating target path {path}: {e}")
                failed_groups += 1
                continue

            existing_items = []
            try:
                existing_items = self.quark.get_folder_list(target_folder_id)
            except Exception as e:
                print(f"Error listing target folder {target_folder_id}: {e}")
                
            files_to_save = []
            for file_item in files_list:
                orig_name = file_item.get("file_name")
                expected_name = file_item["expected_name"]
                size = file_item.get("size")
                
                # Check duplicate by comparing size or names
                matched_existing = None
                for ext_item in existing_items:
                    if ext_item.get("file_type") != 1:
                        continue
                    if ext_item.get("size") == size or ext_item.get("file_name").lower() == expected_name.lower() or ext_item.get("file_name").lower() == orig_name.lower():
                        matched_existing = ext_item
                        break
                        
                if matched_existing:
                    print(f"Skipping duplicate file: {orig_name} (Size: {size})")
                    # Correct old filename if it does not match standard expected name (consistent naming for supplementary batches)
                    current_name = matched_existing.get("file_name")
                    if current_name != expected_name:
                        print(f"Correcting name of existing file in target folder: '{current_name}' -> '{expected_name}'")
                        self.quark.rename_file(matched_existing.get("fid"), expected_name)
                    continue
                    
                files_to_save.append(file_item)
                
            if not files_to_save:
                print(f"All files in group {path} already exist. Skipping save.")
                saved_paths.append('/'.join(path))
                continue
                
            fids = [item.get("fid") for item in files_to_save]
            fid_tokens = [item.get("share_fid_token") for item in files_to_save]
            
            report(f"🚀 正在转存 {len(fids)} 个文件到云盘: {'/'.join(path)} ...")
            success = self.quark.save_share(pwd_id, stoken, fids, fid_tokens, target_folder_id)
            if not success:
                print(f"Failed to save files to target folder {path}")
                failed_groups += 1
                continue
                
            report(f"🏷️ 正在等待同步并执行 Emby 标准重命名: {'/'.join(path)}")
            import time
            saved_items = []
            for _ in range(5):
                saved_items = self.quark.get_folder_list(target_folder_id)
                current_saved_names = {item.get("file_name").lower() for item in saved_items}
                found_count = 0
                for item in files_to_save:
                    if item.get("file_name").lower() in current_saved_names:
                        found_count += 1
                if found_count >= len(files_to_save):
                    break
                time.sleep(1)
                
            saved_items = self.quark.get_folder_list(target_folder_id)
            for item in saved_items:
                orig_name = item.get("file_name")
                
                matched_expected_name = None
                for fs in files_to_save:
                    if fs.get("file_name").lower() == orig_name.lower():
                        matched_expected_name = fs["expected_name"]
                        break
                        
                if matched_expected_name and matched_expected_name != orig_name:
                    self.quark.rename_file(item.get("fid"), matched_expected_name)
                    
            # Check for missing TV episodes in the directory
            if path and path[0] == "TV":
                saved_items = self.quark.get_folder_list(target_folder_id)
                all_episodes = set()
                for item in saved_items:
                    if item.get("file_type") == 1:
                        fname = item.get("file_name", "")
                        m = re.search(r'- S\d+E(\d+)\b', fname, re.IGNORECASE)
                        if m:
                            all_episodes.add(int(m.group(1)))
                        else:
                            ep = self.guess_episode(fname)
                            if ep:
                                all_episodes.add(int(ep[1:]))
                if all_episodes:
                    max_ep = max(all_episodes)
                    if max_ep <= 100:
                        missing = [e for e in range(1, max_ep + 1) if e not in all_episodes]
                        if missing:
                            missing_str = ", ".join(map(str, missing))
                            missing_reports.append(f"【{'/'.join(path)}】缺失集数：第 {missing_str} 集")
                    
            saved_paths.append('/'.join(path))

        if failed_groups == total_groups:
            return "Failed to save files to Quark Drive."
            
        final_msg = f"Successfully saved in: {', '.join(saved_paths)}"
        success_text = f"🎉 保存并重命名成功！已分类存入:\n" + "\n".join([f"- {p}" for p in saved_paths])
        if missing_reports:
            success_text += "\n\n⚠️ **检测到剧集可能不完整**：\n" + "\n".join([f"- {r}" for r in missing_reports]) + "\n*提示：您可以搜索其他资源，再次转存到相同目录以补充缺失剧集。*"
            final_msg += f"\nWarning: Incomplete episodes detected:\n" + "\n".join([f"- {r}" for r in missing_reports])
            
        report(success_text)
        return final_msg
