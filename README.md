# Python 网站镜像脚本

一个 Python 脚本，用于下载网站的静态内容（HTML、CSS、JavaScript、图片等），并重写内部链接以创建一个可在本地浏览的镜像副本。脚本还包含一个简单的 HTTP 服务器，方便在本地查看镜像效果。

## 功能特性

* **递归下载：** 抓取并下载目标网站的资源（HTML、CSS、JS、图片等）。
* **本地链接重写：** 自动尝试重写 HTML 中的绝对和相对链接（`<a>`、`<link>`、`<img>`、`<script>` 标签中的链接），使其指向本地下载的文件，从而实现离线浏览。
* **遵守 robots.txt：** 可选遵守目标网站的 `robots.txt` 文件（默认启用）。
    * 检查 `User-Agent` 规则。
    * 尝试遵守 `Crawl-delay` 指令。
* **模拟目录结构：** 创建与原网站路径结构相对应的本地目录结构。
* **内置 HTTP 服务器：** 在本地端口（默认为 `localhost:0712`）提供镜像内容，方便查看。
* **可配置：**
    * 目标 URL。
    * 本地下载目录。
    * 本地服务器端口。
    * 是否遵守 `robots.txt` 的开关。
* **自定义 User-Agent：** 请求时使用自定义的 User-Agent (`MirrorBot/1.0`)。

## 先决条件

* Python 3.7+
* `pip` (Python 包安装器)

## 安装

1.  **克隆仓库（或下载脚本）**

2.  **安装所需的 Python 库：**
    ```bash
    pip install requests beautifulsoup4
    ```
    或者，使用 `requirements.txt` 文件：
    ```bash
    pip install -r requirements.txt
    ```

## 配置

用文本编辑器打开 Python 脚本（例如 `mirror_site.py`），修改文件顶部的配置变量：


# --- 配置 ---
TARGET_URL = "[http://example.com](http://example.com)"  # 请修改为你想要镜像的网站URL
DOWNLOAD_DIR = "mirrored_site"    # 镜像文件将保存到的目录名
SERVER_PORT = 712                 # 本地查看服务器的端口
RESPECT_ROBOTS_TXT = True         # 设置为 False 则忽略 robots.txt (不建议用于公共网站)
TARGET_URL: 您希望镜像的网站的完整 URL（包括 http:// 或 https://）。
DOWNLOAD_DIR: 将在脚本所在目录中创建的文件夹名称，用于存储镜像文件。
SERVER_PORT: 用于查看镜像的本地 HTTP 服务器将运行的端口。
RESPECT_ROBOTS_TXT:布尔值。如果为 True，脚本将尝试获取并遵守目标站点的 robots.txt 规则。设置为 False 则禁用此功能（请谨慎使用并尊重网站条款）。
## 使用方法
1.确保您已在脚本中配置了 TARGET_URL 和其他设置。
2.在终端中运行脚本：
  ```bash
  
  python mirror_site.py
  
  ```
3.脚本将开始将文件下载到指定的 DOWNLOAD_DIR。您将在控制台中看到进度消息。
4.镜像过程完成后，本地 HTTP 服务器将启动。
5.打开您的网络浏览器，访问 http://localhost:端口号（例如，如果使用默认端口，则为 http://localhost:0712）以查看镜像的网站。
6。要在终端中停止脚本和本地服务器，请按 Ctrl+C。
## 工作原理
1.初始化： 脚本从 TARGET_URL 开始。
2.robots.txt (可选)： 如果启用，它会获取并解析目标域名的 robots.txt 文件，以检查权限和抓取延迟。
3.内容获取： 使用 requests 库下载 URL 的内容。
4.解析 (HTML)： 对于 HTML 文件，使用 BeautifulSoup4 解析内容。
5.链接发现与重写：
  .查找常见标签中的链接（href、src 属性）。
  .将找到的 URL 转换为绝对 URL，以判断它们是否属于同一域名。
  .将新的、属于同一域名的 URL 添加到队列中以供进一步抓取。
  .重写已下载的 HTML 文件中的链接，使其指向 DOWNLOAD_DIR 内新的相对本地路径。
6.文件保存： 文件被保存到模仿原始站点路径的本地目录结构中。文件名会进行无害化处理。
7.迭代： 对从同一域名发现并加入队列的所有 URL 重复此过程。
8.本地服务器： 抓取完成后，Python 的 http.server 模块在指定的本地端口上提供 DOWNLOAD_DIR 的内容。
## 局限性与注意事项
静态网站： 此脚本主要为内容大多为静态的网站设计。
动态内容： 严重依赖 JavaScript 渲染内容、通过 AJAX 调用加载数据或具有复杂客户端路由的网站可能无法正确镜像。脚本不执行 JavaScript。
CSS/JS 中的链接： 虽然它会重写 <script> 标签中的 src 属性和 <link> 标签中的 href，但它不会解析 CSS 或 JavaScript 文件以查找并重写内部 URL（例如 CSS 中的 url()，或 JS 中的动态字符串 URL）。
需要登录/会话的内容： 无法镜像需要登录或通过复杂交互建立会话才能访问的内容。
资源消耗： 镜像大型网站可能非常耗时，并消耗大量带宽和磁盘空间。
错误处理： 对网络请求进行了基本的错误处理，但复杂的服务器错误或非标准行为可能无法优雅处理。
道德使用： 请负责任地使用此工具。始终遵守网站的服务条款和版权。请勿将此工具用于任何恶意目的或使服务器超载。最好在您拥有或获得明确镜像许可的网站上使用。

## 许可证
本项目采用 MIT 许可证授权 - 有关详细信息，请参阅 LICENSE.md 文件。
