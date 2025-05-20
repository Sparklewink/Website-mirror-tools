import os
import re
import shutil
from urllib.parse import urljoin, urlparse, unquote
from urllib import robotparser  # 新增
from pathlib import Path
import http.server
import socketserver
import threading
import time

import requests
from bs4 import BeautifulSoup

# --- 配置 ---
TARGET_URL = "http://example.com"  # 请修改为你想要镜像的网站URL
DOWNLOAD_DIR = "mirrored_site" #下载文件夹
SERVER_PORT = 712 #端口号，可自己修改
RESPECT_ROBOTS_TXT = False  # True: 遵守robots.txt, False: 忽略robots.txt

# 全局变量
urls_to_visit = set()
visited_urls = set()
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 MirrorBot/1.0"
})

robot_parsers = {}  # 存储 RobotFileParser 实例 {domain: parser}
last_request_times = {}  # 存储每个域名的最后请求时间 {domain: timestamp}


class AllowAllRobotParserPlaceholder:
    """一个在robots.txt读取失败时使用的占位解析器，允许所有操作。"""

    def can_fetch(self, useragent, url):
        return True

    def crawl_delay(self, useragent):
        return None

    def request_rate(self, useragent):  # (requests, seconds)
        return None


def get_robot_parser_for_url(url_str):
    """获取或创建、读取并缓存指定URL域名的RobotFileParser。"""
    parsed_url = urlparse(url_str)
    domain = parsed_url.netloc
    robots_url = f"{parsed_url.scheme}://{domain}/robots.txt"

    if domain not in robot_parsers:
        print(f"    [i] 正在为 {domain} 读取 robots.txt")
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception as e:
            print(f"    [!] 读取 {domain} 的 robots.txt 失败: {e}. 假设允许所有。")
            rp = AllowAllRobotParserPlaceholder()
        robot_parsers[domain] = rp
    return robot_parsers[domain]


def sanitize_path(path_segment):
    """清理路径段，移除不安全字符，并将查询参数等作为文件名的一部分（简化处理）"""
    decoded_segment = unquote(path_segment)
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', decoded_segment)
    sanitized = sanitized.strip('. ')
    if not sanitized:
        return "_"
    return sanitized


def get_local_path(base_url_netloc, current_url_str, download_dir_base):
    """根据URL生成本地文件路径"""
    parsed_url = urlparse(current_url_str)
    path_parts = [sanitize_path(part) for part in parsed_url.path.strip('/').split('/') if part]

    filename = "index.html"
    if path_parts:
        if '.' in path_parts[-1] or len(path_parts[-1]) > 50:  # Heuristic for filename-like part
            filename = path_parts.pop()

    if parsed_url.query:
        filename += "_" + sanitize_path(parsed_url.query)
    if parsed_url.fragment:
        filename += "_" + sanitize_path(parsed_url.fragment)

    if not filename and not path_parts:
        filename = "index.html"
    elif not filename and path_parts:
        filename = "index.html"

    local_dir = Path(download_dir_base)
    for part in path_parts:
        local_dir = local_dir / part

    return local_dir / filename, local_dir


def download_and_process_url(url_to_fetch, base_domain, download_root):
    """下载URL内容，如果是HTML则解析并查找更多链接。返回True表示成功，False表示失败。"""
    print(f"[*] 正在访问: {url_to_fetch}")

    try:
        response = session.get(url_to_fetch, timeout=15, stream=True)  # Increased timeout
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[!] 请求失败 {url_to_fetch}: {e}")
        visited_urls.add(url_to_fetch)  # 标记为已访问，即使失败，以避免重试
        return False

    content_type = response.headers.get('content-type', '').lower()
    local_filepath, local_dir = get_local_path(base_domain, url_to_fetch, download_root)

    local_dir.mkdir(parents=True, exist_ok=True)

    with open(local_filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"    -> 已保存到: {local_filepath}")
    visited_urls.add(url_to_fetch)  # 标记为已访问（成功下载后）

    if 'text/html' in content_type:
        encoding = response.encoding or 'utf-8'
        try:
            with open(local_filepath, 'r', encoding=encoding, errors='replace') as f_read:
                soup = BeautifulSoup(f_read.read(), 'html.parser')
        except Exception as e:
            print(f"[!] 解析HTML失败 {local_filepath}: {e}")
            return True  # 文件已下载，但解析失败

        modified = False
        for tag_name, attr_name in [('a', 'href'), ('link', 'href'),
                                    ('img', 'src'), ('script', 'src')]:
            for tag in soup.find_all(tag_name):
                attr_value = tag.get(attr_name)
                if not attr_value:
                    continue

                absolute_url = urljoin(url_to_fetch, attr_value)
                parsed_absolute_url = urlparse(absolute_url)

                if parsed_absolute_url.netloc == base_domain and \
                        parsed_absolute_url.scheme in ['http', 'https']:

                    target_local_path_obj, _ = get_local_path(base_domain, absolute_url, download_root)
                    current_file_dir_obj = local_filepath.parent

                    try:
                        relative_new_path = os.path.relpath(target_local_path_obj, current_file_dir_obj)
                        relative_new_path = relative_new_path.replace(os.sep, '/')

                        if tag[attr_name] != relative_new_path:
                            # print(f"    🔗 更新链接: {tag[attr_name]} -> {relative_new_path}")
                            tag[attr_name] = relative_new_path
                            modified = True
                    except ValueError as ve:
                        print(f"[!] 无法计算相对路径: {target_local_path_obj} from {current_file_dir_obj} - {ve}")

                    if absolute_url not in visited_urls and absolute_url not in urls_to_visit:
                        urls_to_visit.add(absolute_url)

        if modified:
            try:
                with open(local_filepath, 'w', encoding=encoding, errors='replace') as f_write:
                    f_write.write(str(soup))
                print(f"    -> 已更新链接并保存: {local_filepath}")
            except Exception as e:
                print(f"[!] 写入修改后的HTML失败 {local_filepath}: {e}")
    return True


def start_mirroring(target_url_str, download_dir_str):
    """主镜像逻辑"""
    download_root_path = Path(download_dir_str)
    if download_root_path.exists():
        print(f"[*] 清理旧的镜像目录: {download_dir_str}")
        shutil.rmtree(download_root_path)
    download_root_path.mkdir(parents=True, exist_ok=True)

    parsed_target_url = urlparse(target_url_str)
    base_domain = parsed_target_url.netloc
    user_agent_for_robots = session.headers.get("User-Agent", "*")

    if not base_domain:
        print(f"[!] 无效的目标URL，无法提取域名: {target_url_str}")
        return

    urls_to_visit.add(target_url_str)

    while urls_to_visit:
        current_url = urls_to_visit.pop()

        if current_url in visited_urls:
            continue

        current_domain = urlparse(current_url).netloc  # Should always be base_domain

        if RESPECT_ROBOTS_TXT:
            rp = get_robot_parser_for_url(current_url)

            if not rp.can_fetch(user_agent_for_robots, current_url):
                print(f"[*] 跳过 (robots.txt禁止): {current_url}")
                visited_urls.add(current_url)  # 标记为已访问，避免重试
                continue

            delay = rp.crawl_delay(user_agent_for_robots)
            if delay:
                last_request_time = last_request_times.get(current_domain, 0)
                wait_time = (last_request_time + delay) - time.time()
                if wait_time > 0:
                    print(f"    [i] 遵守Crawl-delay: 等待 {wait_time:.2f}s ({current_domain})")
                    time.sleep(wait_time)

        download_successful = download_and_process_url(current_url, base_domain, download_root_path.resolve())

        if RESPECT_ROBOTS_TXT and download_successful:  # 记录成功请求的时间
            last_request_times[current_domain] = time.time()

        # 可选：即使不遵守robots.txt，也加一个小延时
        # if not (RESPECT_ROBOTS_TXT and delay): # 如果没有 crawl-delay 控制
        #     time.sleep(0.1) # 通用小延时

    print("\n[*] 镜像过程完成!")
    print(f"[*] 文件保存在: {download_root_path.resolve()}")


def run_server(port, directory):
    """启动一个简单的HTTP服务器来查看镜像效果"""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    # 确保目录存在才启动服务器
    if not Path(directory).exists():
        print(f"[!] 错误：镜像目录 '{directory}' 不存在，无法启动服务器。")
        return

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"\n[*] 在 http://localhost:{port} 启动本地服务器")
        print(f"[*] 服务目录: {directory}")
        print("[*] 按 Ctrl+C 停止服务器。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] 服务器已停止。")
            httpd.shutdown()
        except OSError as e:
            print(f"\n[!] 服务器启动失败 (端口 {port} 可能已被占用): {e}")


if __name__ == "__main__":
    if not TARGET_URL or TARGET_URL == "http://example.com":  # 提醒用户修改
        print("[-] 请编辑脚本，修改 TARGET_URL 为你想要镜像的网站。")
        print("[-] 你也可以修改 RESPECT_ROBOTS_TXT (当前为 {}) 来控制是否遵守robots.txt。".format(RESPECT_ROBOTS_TXT))
    else:
        start_mirroring(TARGET_URL, DOWNLOAD_DIR)

        # 确保DOWNLOAD_DIR是Path对象以便resolve()
        # 并且在启动服务器前检查目录是否存在
        server_dir = Path(DOWNLOAD_DIR).resolve()
        if server_dir.exists():
            server_thread = threading.Thread(target=run_server, args=(SERVER_PORT, server_dir))
            server_thread.daemon = True
            server_thread.start()

            try:
                while server_thread.is_alive():
                    server_thread.join(timeout=1)
            except KeyboardInterrupt:
                print("\n[*] 收到退出信号，正在关闭...")
        else:
            print(f"\n[!] 镜像目录 '{DOWNLOAD_DIR}' 未创建或为空，服务器未启动。")