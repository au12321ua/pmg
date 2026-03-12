"""
加密工具模块
"""

import os
import base64
import secrets
import hashlib
import hmac
import json
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import argon2


class CryptoManager:
    """加密管理器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "config.json")
        self.data_file = os.path.join(data_dir, "data.enc")
        self.master_key = None
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_config(self):
        """保存配置"""
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return 'salt' in self.config and 'master_hash' in self.config

    def initialize(self, master_password: str) -> bool:
        """初始化"""
        try:
            # 生成盐值
            salt = secrets.token_bytes(32)

            # 使用Argon2id哈希主密码
            hasher = argon2.PasswordHasher(
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                salt_len=32,
                type=argon2.Type.ID  # Argon2id
            )
            master_hash = hasher.hash(master_password)

            # 保存配置
            self.config.update({
                'salt': base64.b64encode(salt).decode(),
                'master_hash': master_hash,
                'initialized_at': datetime.now().isoformat(),
                'version': '1.0'
            })

            self._save_config()

            # 派生主密钥
            self._derive_master_key(master_password, salt)

            # 创建空数据文件
            self._save_entries({})

            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def _derive_master_key(self, master_password: str, salt: bytes) -> bytes:
        """派生主密钥"""
        kdf = Scrypt(
            salt=salt,
            length=32,
            n=2**14,
            r=8,
            p=1
        )
        self.master_key = kdf.derive(master_password.encode())
        return self.master_key

    def verify_master_password(self, master_password: str) -> bool:
        """验证主密码"""
        try:
            if not self.is_initialized():
                return False

            # 验证Argon2哈希
            hasher = argon2.PasswordHasher()
            stored_hash = self.config['master_hash']
            hasher.verify(stored_hash, master_password)

            # 派生主密钥
            salt = base64.b64decode(self.config['salt'])
            self._derive_master_key(master_password, salt)

            return True

        except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.VerificationError):
            return False
        except Exception:
            return False

    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """更改主密码"""
        try:
            if not self.verify_master_password(old_password):
                return False

            # 加载当前数据
            entries = self._load_entries()

            # 生成新盐值
            new_salt = secrets.token_bytes(32)

            # 哈希新密码
            hasher = argon2.PasswordHasher(
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                salt_len=32,
                type=argon2.Type.ID
            )
            new_master_hash = hasher.hash(new_password)

            # 更新配置
            self.config.update({
                'salt': base64.b64encode(new_salt).decode(),
                'master_hash': new_master_hash,
                'updated_at': datetime.now().isoformat()
            })

            # 派生新主密钥
            self._derive_master_key(new_password, new_salt)

            # 重新加密所有数据
            self._save_entries(entries)

            # 保存配置
            self._save_config()

            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def _encrypt_data(self, data: bytes) -> Tuple[bytes, bytes]:
        """加密数据"""
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(self.master_key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce, ciphertext

    def _decrypt_data(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """解密数据"""
        aesgcm = AESGCM(self.master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _save_entries(self, entries: Dict):
        """保存条目"""
        try:
            # 序列化并加密
            json_data = json.dumps(entries).encode()
            nonce, ciphertext = self._encrypt_data(json_data)

            # 保存到文件
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.data_file, 'wb') as f:
                f.write(nonce + ciphertext)

        except Exception as e:
            print(f"Error saving entries: {e}")
            raise

    def _load_entries(self) -> Dict:
        """加载条目"""
        try:
            if not os.path.exists(self.data_file):
                return {}

            with open(self.data_file, 'rb') as f:
                data = f.read()

            if len(data) < 12:
                return {}

            nonce = data[:12]
            ciphertext = data[12:]

            # 解密数据
            json_data = self._decrypt_data(nonce, ciphertext)
            return json.loads(json_data.decode())

        except Exception as e:
            print(f"Error loading entries: {e}")
            return {}

    def add_entry(self, site: str, username: str, password: str) -> bool:
        """添加条目"""
        try:
            entries = self._load_entries()

            # 加密密码
            encrypted_password = self._encrypt_password(password)

            entries[site] = {
                'username': username,
                'password': encrypted_password,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            self._save_entries(entries)
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def get_entry(self, site: str) -> Optional[Tuple[str, str]]:
        """获取条目"""
        try:
            entries = self._load_entries()

            if site not in entries:
                return None

            entry = entries[site]
            password = self._decrypt_password(entry['password'])

            return entry['username'], password

        except Exception:
            return None

    def list_entries(self) -> Dict[str, str]:
        """列出所有条目"""
        try:
            entries = self._load_entries()
            return {site: entry['username'] for site, entry in entries.items()}
        except Exception:
            return {}

    def delete_entry(self, site: str) -> bool:
        """删除条目"""
        try:
            entries = self._load_entries()

            if site not in entries:
                return False

            del entries[site]
            self._save_entries(entries)
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def _encrypt_password(self, password: str) -> Dict:
        """加密单个密码"""
        # 为每个密码生成独立的盐值
        salt = secrets.token_bytes(16)

        # 使用HMAC-SHA256派生密钥
        key = hmac.new(self.master_key, salt, hashlib.sha256).digest()

        # 加密密码
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, password.encode(), None)

        return {
            'salt': base64.b64encode(salt).decode(),
            'nonce': base64.b64encode(nonce).decode(),
            'ciphertext': base64.b64encode(ciphertext).decode()
        }

    def _decrypt_password(self, encrypted_data: Dict) -> str:
        """解密单个密码"""
        salt = base64.b64decode(encrypted_data['salt'])
        nonce = base64.b64decode(encrypted_data['nonce'])
        ciphertext = base64.b64decode(encrypted_data['ciphertext'])

        # 派生相同的密钥
        key = hmac.new(self.master_key, salt, hashlib.sha256).digest()

        # 解密密码
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode()

    @staticmethod
    def generate_password(length: int = 16) -> str:
        """生成强密码"""
        if length < 8:
            length = 8

        import string

        # 字符集
        lowercase = string.ascii_lowercase
        uppercase = string.ascii_uppercase
        digits = string.digits
        symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"

        # 确保每种类型至少有一个字符
        password_chars = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(symbols)
        ]

        # 填充剩余长度
        all_chars = lowercase + uppercase + digits + symbols
        password_chars += [secrets.choice(all_chars) for _ in range(length - 4)]

        # 随机打乱
        secrets.SystemRandom().shuffle(password_chars)

        return ''.join(password_chars)