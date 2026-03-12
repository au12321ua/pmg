"""
会话管理模块
"""

import os
import json
import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional


class SessionManager:
    """会话管理器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.session_file = os.path.join(data_dir, "session.token")
        self.session_key = None
        self.session_data = None

    def create_session(self, master_key: bytes, duration_hours: int = 1) -> str:
        """创建会话"""
        # 生成会话密钥
        self.session_key = hashlib.sha256(master_key + b"session").digest()

        # 创建会话数据
        expires_at = datetime.now() + timedelta(hours=duration_hours)
        session_data = {
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat()
        }

        # 签名会话
        token = self._sign_session(session_data)

        # 保存会话
        self._save_session(token)
        self.session_data = session_data

        return token

    def load_session(self, master_key: bytes) -> bool:
        """加载会话"""
        try:
            if not os.path.exists(self.session_file):
                return False

            with open(self.session_file, 'r') as f:
                token = f.read().strip()

            # 验证会话
            self.session_key = hashlib.sha256(master_key + b"session").digest()
            session_data = self._verify_session(token)

            if not session_data:
                return False

            # 检查是否过期
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if datetime.now() > expires_at:
                self.clear_session()
                return False

            self.session_data = session_data
            return True

        except Exception:
            return False

    def clear_session(self):
        """清除会话"""
        self.session_data = None
        self.session_key = None
        if os.path.exists(self.session_file):
            os.remove(self.session_file)

    def is_valid(self) -> bool:
        """检查会话是否有效"""
        if not self.session_data:
            return False

        try:
            expires_at = datetime.fromisoformat(self.session_data['expires_at'])
            return datetime.now() <= expires_at
        except Exception:
            return False

    def renew_session(self, duration_hours: int = 1) -> bool:
        """续期会话"""
        if not self.session_data or not self.session_key:
            return False

        try:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
            self.session_data['expires_at'] = expires_at.isoformat()

            token = self._sign_session(self.session_data)
            self._save_session(token)
            return True

        except Exception:
            return False

    def _sign_session(self, session_data: dict) -> str:
        """签名会话数据"""
        # 序列化数据
        data_json = json.dumps(session_data, sort_keys=True).encode()

        # 计算HMAC签名
        signature = hmac.new(self.session_key, data_json, hashlib.sha256).digest()

        # 组合数据+签名
        combined = data_json + b"." + signature

        # Base64编码
        return base64.b64encode(combined).decode()

    def _verify_session(self, token: str) -> Optional[dict]:
        """验证会话令牌"""
        try:
            # Base64解码
            combined = base64.b64decode(token)

            # 分离数据和签名
            parts = combined.split(b".", 1)
            if len(parts) != 2:
                return None

            data_json, signature = parts

            # 验证签名
            expected_signature = hmac.new(self.session_key, data_json, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected_signature):
                return None

            # 解析数据
            return json.loads(data_json.decode())

        except Exception:
            return None

    def _save_session(self, token: str):
        """保存会话令牌"""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.session_file, 'w') as f:
            f.write(token)

    def get_remaining_time(self) -> Optional[timedelta]:
        """获取剩余时间"""
        if not self.session_data:
            return None

        try:
            expires_at = datetime.fromisoformat(self.session_data['expires_at'])
            remaining = expires_at - datetime.now()
            return max(remaining, timedelta(0))
        except Exception:
            return None