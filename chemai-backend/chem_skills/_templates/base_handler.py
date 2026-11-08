"""
Base Skill Handler
所有 Skill Handler 继承此基类，保证调用方式一致
"""
import requests
from typing import Any, Dict, Optional


class BaseSkillHandler:
    """Chem Skill Handler 基类"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.timeout = 30.0

    def _make_request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """统一的 HTTP 请求方法（同步）"""
        url = f"{self.base_url}{path}"
        response = requests.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 请求"""
        return self._make_request("GET", path, params=params)

    def post(
        self, path: str, json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST 请求"""
        return self._make_request("POST", path, json_data=json_data)

    def put(
        self, path: str, json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """PUT 请求"""
        return self._make_request("PUT", path, json_data=json_data)

    def delete(self, path: str) -> Dict[str, Any]:
        """DELETE 请求"""
        return self._make_request("DELETE", path)
