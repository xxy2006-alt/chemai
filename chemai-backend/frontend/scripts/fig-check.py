# fig-check.py — 模拟浏览器请求真题图片（仅编码非 ASCII，保留斜杠）
import urllib.request
from urllib.parse import quote

url = "http://127.0.0.1:8001/static/figures/" + quote("全国卷", safe="") + "/2020/figures/633625dfe5370c0abe9543cb785143ecf0a61e149e01701d1c13bc5f328ecabf.jpg"
print("URL:", url)
try:
    resp = urllib.request.urlopen(url, timeout=5)
    print("status:", resp.status, "| bytes:", len(resp.read()))
except Exception as e:
    print("FAIL:", e)

# 对照：直接带前缀目录路径（应命中直接路径分支）
url2 = "http://127.0.0.1:8001/static/figures/" + quote("01_全国卷", safe="") + "/2020/figures/633625dfe5370c0abe9543cb785143ecf0a61e149e01701d1c13bc5f328ecabf.jpg"
try:
    resp2 = urllib.request.urlopen(url2, timeout=5)
    print("prefix URL status:", resp2.status, "| bytes:", len(resp2.read()))
except Exception as e:
    print("prefix FAIL:", e)
