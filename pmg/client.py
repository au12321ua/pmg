"""
客户端模块
"""

import os
import sys
import json
import logging
import getpass
from typing import Optional, Dict, Any
import uuid

from .daemon import DaemonManager
from .ipc import IPCClient, Message, MessageType
from .crypto import CryptoManager


class PMGClientError(Exception):
    """客户端错误"""
    pass


class PMGClient:
    """PMG客户端"""

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化客户端

        Args:
            data_dir: 数据目录，如果为None则使用默认目录
        """
        if data_dir is None:
            if os.name == 'nt':  # Windows
                self.data_dir = os.path.join(os.environ.get('APPDATA', ''), '.pmg')
            else:  # Linux/macOS
                self.data_dir = os.path.join(os.path.expanduser('~'), '.pmg')
        else:
            self.data_dir = data_dir

        os.makedirs(self.data_dir, exist_ok=True)

        # 日志设置
        self.log_file = os.path.join(self.data_dir, 'client.log')
        self._setup_logging()

        self.logger = logging.getLogger(__name__)

        # 加密器
        self.crypto = CryptoManager(self.data_dir)

        # IPC客户端
        self.ipc_client = None
        self.daemon_manager = DaemonManager(self.data_dir)

    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stderr)
            ]
        )

    def _get_socket_path(self) -> Optional[str]:
        """获取守护进程socket路径"""
        info = self.daemon_manager.get_daemon_info()
        if not info or not info.socket_path:
            return None
        return info.socket_path

    def start_daemon(self) -> bool:
        """启动守护进程"""
        if self.daemon_manager.is_running():
            self.logger.debug("Daemon is already running")
            return True
        self.logger.info("Starting daemon...")
        return self.daemon_manager.start()

    def stop_daemon(self) -> bool:
        """停止守护进程"""
        if not self.daemon_manager.is_running():
            self.logger.debug("Daemon is not running")
            return True
        self.logger.info("Stopping daemon...")
        return self.daemon_manager.stop()

    def connect(self) -> bool:
        """连接到守护进程"""
        import time

        # 首先尝试获取socket路径
        socket_path = self._get_socket_path()

        # 如果daemon未运行，尝试启动
        if not socket_path:
            self.logger.warning("Daemon is not running, attempting to start...")
            if not self.start_daemon():
                self.logger.error("Failed to start daemon")
                return False

            # 等待daemon启动
            for _ in range(5):
                time.sleep(0.5)
                socket_path = self._get_socket_path()
                if socket_path:
                    break
            else:
                self.logger.error("Daemon started but socket path not found")
                return False

        self.ipc_client = IPCClient(socket_path)
        try:
            connected = self.ipc_client.connect(timeout=2.0)
            if connected:
                self.logger.debug(f"Connected to daemon at {socket_path}")
                return True
            else:
                self.logger.error("Failed to connect to daemon")
                return False
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return False

    def _send_command(self, command: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送命令到守护进程"""
        if not self.ipc_client:
            if not self.connect():
                raise PMGClientError("Not connected to daemon")

        message = Message(
            id=str(uuid.uuid4()),
            type=MessageType.REQUEST,
            command=command,
            args=args or {}
        )

        response = self.ipc_client.send_message(message, timeout=30.0)
        if not response:
            raise PMGClientError("No response from daemon")

        if response.type == MessageType.ERROR:
            raise PMGClientError(f"Command failed: {response.error}")

        if response.type != MessageType.RESPONSE:
            raise PMGClientError(f"Unexpected response type: {response.type}")

        return response.data or {}

    def init(self, password: str, confirm_password: str) -> bool:
        """初始化（本地处理，不通过daemon）"""
        try:
            # 检查是否已初始化
            if self.crypto.is_initialized():
                self.logger.warning("Already initialized")
                return True

            # 验证密码
            if password != confirm_password:
                self.logger.error("Passwords do not match")
                return False

            if len(password) < 8:
                self.logger.error("Password must be at least 8 characters")
                return False

            # 本地初始化
            success = self.crypto.initialize(password)
            if success:
                self.logger.info("Initialized successfully")
            else:
                self.logger.error("Initialization failed")

            return success
        except Exception as e:
            self.logger.error(f"Init failed: {e}")
            return False

    def login(self, password: str) -> bool:
        """登录"""
        try:
            # 验证密码
            if not self.crypto.verify_master_password(password):
                raise PMGClientError("Invalid password")
            else:
                # 启动daemon
                if not self.daemon_manager.is_running():
                    if not self.daemon_manager.start():
                        raise PMGClientError("Failed to start daemon")

                # 连接通道
                socket_path = self.daemon_manager.get_daemon_info().socket_path
                self.ipc_client = IPCClient(socket_path)

            result = self._send_command('login', {'password': password})
            if not result.get('success'):
                self.logger.error(f"Login failed: {result.get('error')}")
                return False
            return True
        except PMGClientError as e:
            self.logger.error(f"Login failed: {e}")
            return False

    def logout(self) -> bool:
        """登出"""
        try:
            # result = self._send_command('logout', {})
            # 关闭daemon
            return self.stop_daemon()

        except PMGClientError as e:
            self.logger.error(f"Logout failed: {e}")
            return False

    def status(self) -> Dict[str, Any]:
        """获取状态"""
        try:
            result = self._send_command('status', {})
            return result
        except PMGClientError as e:
            self.logger.error(f"Status check failed: {e}")
            return {'authenticated': False, 'error': str(e)}

    def add(self, site: str, username: str, password: str) -> bool:
        """添加密码"""
        try:
            result = self._send_command('add', {
                'site': site,
                'username': username,
                'password': password
            })
            return result.get('success', False)
        except PMGClientError as e:
            self.logger.error(f"Add failed: {e}")
            return False

    def get(self, site: str) -> Optional[Dict[str, str]]:
        """获取密码"""
        try:
            result = self._send_command('get', {'site': site})
            if result.get('success'):
                return {
                    'site': result.get('site'),
                    'username': result.get('username'),
                    'password': result.get('password')
                }
            else:
                return None
        except PMGClientError as e:
            self.logger.error(f"Get failed: {e}")
            return None

    def list(self) -> Dict[str, str]:
        """列出所有站点"""
        try:
            result = self._send_command('list', {})
            if result.get('success'):
                return result.get('entries', {})
            else:
                return {}
        except PMGClientError as e:
            self.logger.error(f"List failed: {e}")
            return {}

    def delete(self, site: str) -> bool:
        """删除站点"""
        try:
            result = self._send_command('delete', {'site': site})
            return result.get('success', False)
        except PMGClientError as e:
            self.logger.error(f"Delete failed: {e}")
            return False

    def gen(self, site: str, username: str, length: int = 16) -> Optional[str]:
        """生成并保存密码"""
        try:
            result = self._send_command('gen', {
                'site': site,
                'username': username,
                'length': length
            })
            if result.get('success'):
                return result.get('password')
            else:
                return None
        except PMGClientError as e:
            self.logger.error(f"Gen failed: {e}")
            return None

    def export(self, filename: str) -> bool:
        """导出数据"""
        try:
            result = self._send_command('export', {'file': filename})
            return result.get('success', False)
        except PMGClientError as e:
            self.logger.error(f"Export failed: {e}")
            return False

    def import_data(self, filename: str) -> bool:
        """导入数据"""
        try:
            result = self._send_command('import', {'file': filename})
            return result.get('success', False)
        except PMGClientError as e:
            self.logger.error(f"Import failed: {e}")
            return False

    def change_password(self, current_password: str, new_password: str, confirm_password: str) -> bool:
        """更改主密码"""
        try:
            result = self._send_command('change_password', {
                'current_password': current_password,
                'new_password': new_password,
                'confirm_password': confirm_password
            })
            if result.get('success'):
                # 密码更改后需要重新登录
                return True
            else:
                return False
        except PMGClientError as e:
            self.logger.error(f"Change password failed: {e}")
            return False

    def close(self):
        """关闭连接"""
        if self.ipc_client:
            self.ipc_client.disconnect()
            self.ipc_client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class InteractivePMGClient(PMGClient):
    """交互式客户端，提供更友好的用户交互"""

    def interactive_login(self) -> bool:
        """交互式登录"""
        print("Login to PMG")
        password = getpass.getpass("Master password: ")
        return self.login(password)

    def interactive_add(self, site: str, username: str) -> bool:
        """交互式添加密码"""
        print(f"Adding entry for {site}")
        password = getpass.getpass(f"Password for {site}: ")
        if not password:
            print("Error: Password cannot be empty")
            return False

        confirm = getpass.getpass(f"Confirm password for {site}: ")
        if password != confirm:
            print("Error: Passwords do not match")
            return False

        return self.add(site, username, password)

    def interactive_gen(self, site: str, username: str, length: int = 16) -> bool:
        """交互式生成密码"""
        print(f"Generating password for {site}")

        result = self.gen(site, username, length)
        if result:
            print(f"Generated password: {result}")
            print(f"Saved to {site}")
            return True
        else:
            print(f"Failed to save to {site}")
            return False

    def interactive_change_password(self) -> bool:
        """交互式更改主密码"""
        print("Change master password")
        current = getpass.getpass("Current password: ")
        new_password = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm new password: ")

        return self.change_password(current, new_password, confirm)
    
    def interactive_delete(self, site) -> bool:
        """交互式删除密码"""
        confirm = input(f"Delete '{site}'? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return True
        else:
            return self.delete(site)