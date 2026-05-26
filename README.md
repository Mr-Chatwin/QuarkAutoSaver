# QuarkAutoSaver - 夸克网盘自动转存与 Emby 媒体库管理工具

`QuarkAutoSaver` 是一个集成了资源搜索、智能刮削、网盘转存、媒体分类和 Emby 标准命名于一体的自动化媒体库整理工具。通过 Telegram Bot 提供交互，支持一键搜索转存，自动将杂乱的网盘分享资源整理为符合 Emby 刮削规范的标准命名与目录结构。

---

## ✨ 核心特性

1. **Telegram 交互与分页展示**：
   * 支持 `/search <影视名>` 搜索资源。
   * 搜索结果采用并排双按钮结构：`[转存 #N]` 和 `[🔗 链接]`，支持直接跳转网页预览原链接评估资源完整性。
   * 支持多页结果快速切换（下一页/上一页）。

2. **三级智能刮削与识别系统**：
   * **TMDB 刮削**：优先检索 TMDB 官方影视元数据（支持自定义代理 URL 及瞬态网络自动重试机制）。
   * **DeepSeek 大模型后备降级**：如果 TMDB 检索失败，系统自动降级调用 DeepSeek 大模型（`deepseek-v4-flash`）对复杂的合集或乱序文件名进行语义分析。
   * **本地去噪清洗**：内置强力正则清洗，自动剥离文件名中的压制组、分辨率、帧率及无用标签，并在中文字符间进行空格合并。

3. **确定性规则优先与大模型纠偏**：
   * 在季数（Season）与集数（Episode）识别中，优先采用本地确定性正则匹配，避免过度依赖大模型。
   * 设有大模型幻觉纠偏机制，当大模型输出的季数与本地精确提取的集数重合时（如把第 5 集错认为了第 5 季），系统会自动识别为幻觉并执行纠错，回退到默认的第一季。

4. **增量/补充保存与命名修正**：
   * 支持补充保存，自动过滤已转存文件（通过比对大小或名称）。
   * **动态命名修正**：在转存过程中，如果发现云盘中已有旧文件存在但命名不标准（例如第一批次转存时因匹配缺失而未被重命名的原始文件名，如 `01x.mkv`），程序会自动将其重命名修正为 Emby 规范名称（如 `S01E01.mkv`），保证多批次保存的文件命名 100% 一致。

5. **剧集缺失校验**：
   * 针对电视剧集类型，在转存成功后会自动对当前目录（包含新旧文件）进行集数查缺，如果检测到漏集（如缺失第 1、16、21 集），会在转存成功消息中明确发出警告。

6. **网络与安全优化**：
   * **防卡死设计**：所有的网络请求与重命名操作均投递至线程池异步执行，保障高并发或网速受限时，Telegram Bot 及 FastAPI 后台不会同步卡死无响应。
   * **防内存泄露**：内置带过期淘汰（TTL 30分钟）和容量限制（Max 1000）的 `SimpleTTLCache` 缓存结构，解决长效运行时的内存溢出隐患。
   * **Cookie 定时巡检与热更新**：支持定时（每6小时）和失败时主动检测 Cookie 有效性。管理员可通过 `/cookie <new_cookie>` 指令进行 Cookie 在线热更新并自动持久化写入 `.env` 文件。

---

## 🛠️ 部署指南

### 1. 克隆或下载本项目
确保您的服务器已安装了 `Docker` 和 `Docker Compose`。

### 2. 准备配置文件 `.env`
复制 `.env.example` 并命名为 `.env`：
```bash
cp .env.example .env
```
按照说明填写相关配置参数：

```ini
# ---- Telegram 配置 ----
# Telegram Bot Token，找 @BotFather 申请
TG_BOT_TOKEN=your_telegram_bot_token_here
# 允许使用搜索与转存的用户 ID，用逗号分隔（留空代表允许所有人使用）
ALLOWED_USERS=123456,789012
# 管理员用户 ID，用逗号分隔（仅管理员可更新 Cookie 并接收失效报警）
ADMIN_USERS=123456

# ---- 夸克网盘配置 ----
# 夸克网盘 Cookie，在网盘网页版控制台的网络请求中获取
QUARK_COOKIE="your_quark_cookie_string"
# 夸克网盘转存的根目录 FID，默认为 0（代表根目录）
QUARK_BASE_FOLDER_ID=0

# ---- TMDB 配置 ----
# TMDB API Key，用于刮削影视元数据
TMDB_API_KEY=your_tmdb_api_key_here
# 可选：TMDB API 请求基础 URL，可修改为代理或镜像站地址（默认为官方地址）
TMDB_API_URL=https://api.themoviedb.org/3

# ---- DeepSeek 大模型配置 (可选，强烈推荐) ----
# 开启大模型降级刮削需要填写 DeepSeek API Key
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_API_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

# ---- 盘搜接口配置 (关键说明) ----
# 本项目使用盘搜提供夸克分享链接的搜索。
# docker-compose 部署中默认集成并启动了一个本地 pansou 容器服务（基于 ghcr.io/fish2018/pansou-web）。
# 
# * 推荐配置 (使用本地 pansou 容器)：
PANSOU_API_URL=http://pansou
# 
# * 备用配置 (若不使用本地容器，可配置为公网公共镜像站)：
# PANSOU_API_URL=https://so.252035.xyz
```

> ⚠️ **关于盘搜服务的部署顺序说明**：
> 本程序高度依赖盘搜（PanSou）接口提供夸克分享链接。本项目的 `docker-compose.yml` 中已经整合了 `pansou-web` 镜像服务。
> - 如果您在 `.env` 中配置 `PANSOU_API_URL=http://pansou`，程序在容器网络启动后，会自动路由请求至同组的本地盘搜镜像。
> - 在首次部署时，确保本地盘搜镜像拉取及启动无网络异常即可。

### 3. 一键部署启动
在项目根目录下执行以下命令构建并启动服务：
```bash
docker compose up --build -d
```
启动后会运行两个容器：
* `quark-auto-saver`：主服务进程（运行 FastAPI API 及 Telegram Bot 服务）
* `pansou`：本地盘搜网盘搜索引擎接口服务

---

## 📖 使用说明

1. 打开您的 Telegram Bot，发送 `/start` 指令。
2. 使用 `/search <电影或电视剧名称>` 搜索资源。
   * 例如：`/search 低智商犯罪`
3. Bot 会自动解析并呈现资源列表。点击 `🔗 链接` 可以在线预览该分享的完整文件树；点击 `转存 #N` 按钮即可启动后台一键转存、分类重命名及文件查缺。
4. 如遇到夸克 Cookie 失效，管理员会收到 Bot 的失效警报，直接向 Bot 发送 `/cookie <新的Cookie内容>` 即可平滑更新配置，无需重启 Docker 容器。

---

## ⚖️ 开源协议与致谢

1. **盘搜 API 服务 (PanSou)**：
   * 本项目默认集成的第三方搜索模块依赖于开源项目 [fish2018/pansou](https://github.com/fish2018/pansou) 提供的接口与容器服务。
   * 该组件遵循 **MIT 许可证**，特此向原作者 [fish2018](https://github.com/fish2018) 致谢。
   * 根据原作者要求，该服务**仅供学习与研究使用，请勿用于任何形式的商业盈利目的**。

2. **本项目协议**：
   * 本项目同样采用 **MIT 许可证** 开源。
