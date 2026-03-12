"""
临时会话管理模块
使用临时文件存储加密的主密钥，支持进程间共享
"""

import os
import json
import base64
import secrets
import tempfile
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TempSessionManager:
    """临时会话管理器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.session_file = os.path.join(data_dir, "temp_session.json")
        self.session_key = None
        self.session_id = None
        self.master_key = None

    def create_temp_session(self, master_key: bytes, session_key: str = None,
                          duration_minutes: int = 10) -> Tuple[str, str]:
        """
        创建临时会话

        Args:
            master_key: 主密钥
            session_key: 会话密钥（可选，自动生成）
            duration_hours: 会话有效期（小时）

        Returns:
            (session_id, session_key) 会话ID和密钥
        """
        # 生成会话ID
        self.session_id = secrets.token_hex(16)

        # 生成或使用提供的会话密钥
        if session_key is None:
            # 生成6位数字会话密钥
            self.session_key = ''.join(secrets.choice('0123456789') for _ in range(6))
        else:
            self.session_key = session_key

        # 保存主密钥
        self.master_key = master_key

        # 创建会话数据
        expires_at = datetime.now() + timedelta(minutes=duration_minutes)
        session_data = {
            'session_id': self.session_id,
            'created_at': datetime.now().isoformat(),
            'expires_at': expires_at.isoformat(),
            'encrypted_master_key': self._encrypt_master_key(master_key, self.session_key)
        }

        # 保存到文件
        self._save_session_data(session_data)

        return self.session_id, self.session_key

    def load_temp_session(self, session_key: str) -> Optional[bytes]:
        """
        加载临时会话

        Args:
            session_key: 会话密钥

        Returns:
            主密钥或None
        """
        try:
            if not os.path.exists(self.session_file):
                return None

            # 加载会话数据
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            # 检查是否过期
            expires_at = datetime.fromisoformat(session_data['expires_at'])
            if datetime.now() > expires_at:
                self.clear_temp_session()
                return None

            # 解密主密钥
            master_key = self._decrypt_master_key(
                session_data['encrypted_master_key'],
                session_key
            )

            if master_key:
                self.session_id = session_data['session_id']
                self.session_key = session_key
                self.master_key = master_key
                return master_key

        except Exception:
            pass

        return None

    def clear_temp_session(self):
        """清除临时会话"""
        self.session_id = None
        self.session_key = None
        self.master_key = None
        if os.path.exists(self.session_file):
            os.remove(self.session_file)

    def is_valid(self) -> bool:
        """检查会话是否有效"""
        if not os.path.exists(self.session_file):
            return False

        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            expires_at = datetime.fromisoformat(session_data['expires_at'])
            return datetime.now() <= expires_at

        except Exception:
            return False

    def get_remaining_time(self) -> Optional[timedelta]:
        """获取剩余时间"""
        try:
            if not os.path.exists(self.session_file):
                return None

            with open(self.session_file, 'r') as f:
                session_data = json.load(f)

            expires_at = datetime.fromisoformat(session_data['expires_at'])
            remaining = expires_at - datetime.now()
            return max(remaining, timedelta(0))

        except Exception:
            return None

    def _encrypt_master_key(self, master_key: bytes, session_key: str) -> str:
        """使用会话密钥简单加密主密钥"""
        # 简单XOR加密（牺牲安全性换取简单性）
        key_bytes = session_key.encode()
        key_len = len(key_bytes)

        # 扩展密钥以匹配主密钥长度
        expanded_key = (key_bytes * (len(master_key) // key_len + 1))[:len(master_key)]

        # XOR加密
        encrypted = bytes(a ^ b for a, b in zip(master_key, expanded_key))

        return base64.b64encode(encrypted).decode()

    def _decrypt_master_key(self, encrypted_data: str, session_key: str) -> Optional[bytes]:
        """使用会话密钥解密主密钥"""
        try:
            # 解码加密数据
            encrypted = base64.b64decode(encrypted_data)

            # 简单XOR解密（与加密相同）
            key_bytes = session_key.encode()
            key_len = len(key_bytes)

            # 扩展密钥以匹配加密数据长度
            expanded_key = (key_bytes * (len(encrypted) // key_len + 1))[:len(encrypted)]

            # XOR解密
            master_key = bytes(a ^ b for a, b in zip(encrypted, expanded_key))

            return master_key

        except Exception:
            return None

    def _save_session_data(self, session_data: dict):
        """保存会话数据"""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

    @staticmethod
    def generate_session_key(length: int = 6) -> str:
        """生成会话密钥"""
        if length <= 0:
            length = 6

        # 生成数字会话密钥
        return ''.join(secrets.choice('0123456789') for _ in range(length))