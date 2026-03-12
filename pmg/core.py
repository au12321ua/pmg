"""
核心逻辑模块
"""

import os
import sys
import getpass
from typing import Optional, Tuple
from .crypto import CryptoManager
from .session import SessionManager


class PasswordManagerCore:
    """密码管理器核心"""

    def __init__(self):
        # 确定数据目录
        if os.name == 'nt':  # Windows
            self.data_dir = os.path.join(os.environ.get('APPDATA', ''), '.pmg')
        else:  # Linux/macOS
            self.data_dir = os.path.join(os.path.expanduser('~'), '.pmg')

        self.crypto = CryptoManager(self.data_dir)
        self.session = SessionManager(self.data_dir)

    def ensure_authenticated(self) -> bool:
        """确保已认证"""
        if not self.session.is_valid():
            print("Error: Not authenticated or session expired")
            print("Use 'pmg login <password>' first")
            return False
        return True

    def login(self, password: str) -> bool:
        """登录"""
        if not self.crypto.verify_master_password(password):
            print("Error: Invalid password")
            return False

        # 创建会话
        self.session.create_session(self.crypto.master_key)
        print("Logged in successfully")
        return True

    def logout(self) -> bool:
        """登出"""
        self.session.clear_session()
        print("Logged out")
        return True

    def status(self) -> bool:
        """查看状态"""
        if self.session.is_valid():
            remaining = self.session.get_remaining_time()
            if remaining:
                minutes = int(remaining.total_seconds() / 60)
                print(f"Authenticated (expires in {minutes} minutes)")
            else:
                print("Authenticated")
            return True
        else:
            print("Not authenticated")
            return False

    def add(self, site: str, username: str) -> bool:
        """添加密码"""
        if not self.ensure_authenticated():
            return False

        # 获取密码
        password = getpass.getpass(f"Password for {site}: ")
        if not password:
            print("Error: Password cannot be empty")
            return False

        # 添加条目
        if self.crypto.add_entry(site, username, password):
            print(f"Added {site}")
            return True
        else:
            print(f"Error: Failed to add {site}")
            return False

    def get(self, site: str) -> bool:
        """获取密码"""
        if not self.ensure_authenticated():
            return False

        # 获取条目
        result = self.crypto.get_entry(site)
        if not result:
            print(f"Error: Site '{site}' not found")
            return False

        username, password = result
        print(f"Site: {site}")
        print(f"Username: {username}")
        print(f"Password: {password}")
        return True

    def list(self) -> bool:
        """列出所有站点"""
        if not self.ensure_authenticated():
            return False

        entries = self.crypto.list_entries()
        if not entries:
            print("No entries found")
            return True

        print("Saved sites:")
        for site, username in entries.items():
            print(f"  {site}: {username}")
        return True

    def delete(self, site: str) -> bool:
        """删除站点"""
        if not self.ensure_authenticated():
            return False

        # 确认删除
        confirm = input(f"Delete '{site}'? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return False

        if self.crypto.delete_entry(site):
            print(f"Deleted {site}")
            return True
        else:
            print(f"Error: Site '{site}' not found")
            return False

    def gen(self, site: str, username: str, length: int = 16) -> bool:
        """生成并保存密码"""
        if not self.ensure_authenticated():
            return False

        # 生成密码
        password = CryptoManager.generate_password(length)
        print(f"Generated password: {password}")

        # 保存
        if self.crypto.add_entry(site, username, password):
            print(f"Saved to {site}")
            return True
        else:
            print(f"Error: Failed to save {site}")
            return False

    def export(self, filename: str) -> bool:
        """导出数据"""
        if not self.ensure_authenticated():
            return False

        try:
            entries = self.crypto._load_entries()
            if not entries:
                print("No data to export")
                return False

            # 解密所有密码
            decrypted_data = {}
            for site, entry in entries.items():
                password = self.crypto._decrypt_password(entry['password'])
                decrypted_data[site] = {
                    'username': entry['username'],
                    'password': password,
                    'created_at': entry.get('created_at', ''),
                    'updated_at': entry.get('updated_at', '')
                }

            # 保存到文件
            import json
            with open(filename, 'w') as f:
                json.dump(decrypted_data, f, indent=2)

            print(f"Exported to {filename}")
            print("WARNING: This file contains plaintext passwords!")
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def import_data(self, filename: str) -> bool:
        """导入数据"""
        if not self.ensure_authenticated():
            return False

        try:
            import json
            with open(filename, 'r') as f:
                data = json.load(f)

            # 导入每个条目
            count = 0
            for site, entry in data.items():
                if self.crypto.add_entry(site, entry['username'], entry['password']):
                    count += 1

            print(f"Imported {count} entries from {filename}")
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False

    def init(self) -> bool:
        """初始化"""
        if self.crypto.is_initialized():
            print("Already initialized")
            return True

        print("First time setup")
        print("Set your master password (remember it, it cannot be recovered)")

        # 获取密码
        while True:
            password = getpass.getpass("Master password: ")
            confirm = getpass.getpass("Confirm master password: ")

            if password != confirm:
                print("Passwords do not match")
                continue

            if len(password) < 8:
                print("Password must be at least 8 characters")
                continue

            break

        # 初始化
        if self.crypto.initialize(password):
            print("Initialized successfully")
            return True
        else:
            print("Initialization failed")
            return False

    def change_password(self) -> bool:
        """更改主密码"""
        if not self.ensure_authenticated():
            return False

        print("Change master password")

        # 获取当前密码
        current = getpass.getpass("Current password: ")
        if not self.crypto.verify_master_password(current):
            print("Error: Invalid current password")
            return False

        # 获取新密码
        while True:
            new_password = getpass.getpass("New password: ")
            confirm = getpass.getpass("Confirm new password: ")

            if new_password != confirm:
                print("Passwords do not match")
                continue

            if len(new_password) < 8:
                print("Password must be at least 8 characters")
                continue

            break

        # 更改密码
        if self.crypto.change_master_password(current, new_password):
            print("Password changed successfully")
            # 重新登录
            self.session.clear_session()
            self.login(new_password)
            return True
        else:
            print("Failed to change password")
            return False