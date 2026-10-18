# 心理危机监测与预警系统 · GitHub Pages

这是独立的静态展示版本。保留首页、本地文本推理、普通用户分析、热点专题分析、模型评测与边界五个栏目。浏览器直接加载本目录中的数据与图表，不需要 Streamlit Cloud、云服务器或模型权重。

## 展示范围

- 指标、样本数、分布与时间统计来自原工程的现有结果，没有重新训练或推理。
- 普通用户发布经人工核验的匿名用户结果、九维概率与阈值、归因证据及脱敏动态；热点专题提供匿名文本、情绪和当前命题立场结果。真实账号、原始平台ID、账号提及、联系方式与原帖链接不导出。
- 用户及热点文本支持筛选、排序、分页、行选择及详情浏览；复核候选按当前阈值筛选，尚不保存人工标签或备注。
- 本地文本推理保留输入界面和分析按钮，按钮不可执行，明确显示“暂未接入模型推理”。输入不上传、不保存，不会产生模型结果。
- 保留原有模型评测与校准计算口径，仅导出汇总值和曲线点。

## 本地预览

在本目录打开终端，运行：

```powershell
py -m http.server 8080 --bind 127.0.0.1
```

打开 `http://localhost:8080`。如果没有 `py`，可使用已安装的 Python 执行同一命令。预览只用于本机；不要通过双击 HTML 文件测试数据读取。8080只是本地预览端口，与 GitHub Pages 公网网址无须对齐。

## 发布到个人 GitHub 账号

1. 新建一个专门的公开仓库，例如 `mental-health-research`。不要上传原始研究工程。
2. 将本目录的**内容**上传至仓库根目录，确保根目录直接包含 `index.html`，而不是再套一层 `github_pages` 文件夹。保留 `.nojekyll`、`assets` 和 `data`。
3. 在仓库的 **Settings → Pages → Build and deployment** 中选择 **Deploy from a branch**，分支选 `main`，目录选 `/(root)`，保存。
4. 等待部署完成，使用 Pages 页面显示的 HTTPS 地址访问。无须设置服务器端口、安装 Python 或上传模型。
5. 用无痕窗口和汇报网络检查栏目、图表、地图、筛选与链接；保留本地原版作为演示备用。

官方操作说明：<https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site>

## 文件与维护

- `index.html`：统一题头、导航、主体与页脚。
- `assets/app.js`、`assets/site.css`：交互和样式。
- `assets/vendor/plotly.min.js`：随站点提供的绘图库，避免依赖外部CDN。
- `data/manifest.json`：专题与数据索引；其他JSON按栏目及专题加载。
- `data/users-cases.json`与`data/event-*-cases.json`：经核验的匿名记录和模型结果。`data/user-posts-*.json`按用户分批保存动态，仅展开所选用户的动态时读取。
- `tools/build_public_data.py`：本地汇总导出工具，默认从同级原工程的 `app` 目录读取结果。仅用于维护，部署时不会执行。
- `tools/verify_public.py`：发布包完整性、隐私字段、路径与统计核对。

在完整工程中，需要重新导出时，可在本目录使用原工程已安装的环境运行：

```powershell
..\app\.venv\Scripts\python.exe -B tools/build_public_data.py
..\app\.venv\Scripts\python.exe -B tools/verify_public.py
```

本目录不记录个人电脑的盘符路径、账户目录或凭据。`tools`和本说明不是网页运行依赖；可保留在仓库中用于维护。不要把模型、原始采集数据、Cookie、密钥、虚拟环境或备份加入仓库。

所有发布数据均可被访问者下载。隐藏表格列、折叠详情或设置源仓库为私有，不是公开页面的数据保护措施。

## 已验证与待验证

本地检查覆盖数据契约、五个栏目、专题切换、统计条件、筛选、图表、地图、桌面及手机宽度、仓库子路径访问。线上仓库尚未创建或上传；GitHub Pages最终网址、现场网络及真实手机体验须在发布后确认。

第三方许可见 `THIRD_PARTY_NOTICES.md`。
