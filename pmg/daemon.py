"""
守护进程管理模块
"""

import os
import sys
import json
import time
import signal
import socket
import struct
import threading
import subprocess
import tempfile
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from .crypto import CryptoManager


class DaemonStatus(Enum):
    """守护进程状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DaemonInfo:
    """守护进程信息"""
    pid: int
    status: DaemonStatus
    start_time: float
    socket_path: str
    data_dir: str


class DaemonManager:
    """守护进程管理器"""

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化守护进程管理器

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

        # 守护进程信息文件
        self.info_file = os.path.join(self.data_dir, 'daemon.json')

        # 日志设置
        self.log_file = os.path.join(self.data_dir, 'daemon.log')
        self._setup_logging()

        # IPC服务器相关
        self.ipc_server = None
        self.command_handler = None

        self.logger = logging.getLogger(__name__)

    def _setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stderr)
            ]
        )

    def get_daemon_info(self) -> Optional[DaemonInfo]:
        """获取守护进程信息"""
        try:
            if not os.path.exists(self.info_file):
                return None

            with open(self.info_file, 'r') as f:
                data = json.load(f)

            return DaemonInfo(
                pid=data['pid'],
                status=DaemonStatus(data['status']),
                start_time=data['start_time'],
                socket_path=data['socket_path'],
                data_dir=data['data_dir']
            )
        except Exception as e:
            self.logger.error(f"Failed to read daemon info: {e}")
            return None

    def save_daemon_info(self, info: DaemonInfo):
        """保存守护进程信息"""
        try:
            data = {
                'pid': info.pid,
                'status': info.status.value if isinstance(info.status, DaemonStatus) else info.status,
                'start_time': info.start_time,
                'socket_path': info.socket_path,
                'data_dir': info.data_dir
            }

            with open(self.info_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save daemon info: {e}")

    def is_running(self) -> bool:
        """检查守护进程是否在运行"""
        info = self.get_daemon_info()
        if not info:
            return False

        # 检查进程是否存在
        try:
            os.kill(info.pid, 0)
            return True
        except Exception:
            return False

    def start(self) -> bool:
        """启动守护进程"""
        if self.is_running():
            self.logger.info("Daemon is already running")
            return True

        self.logger.info("Starting daemon...")

        # 生成socket路径
        socket_path = self._get_socket_path()

        # 启动守护进程子进程
        try:
            # 使用当前Python解释器以模块方式启动守护进程
            cmd = [sys.executable, "-m", "pmg.daemon_main", "--data-dir", self.data_dir, "--socket-path", socket_path]

            # 在后台启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )

            # 等待守护进程启动
            time.sleep(1)

            # 检查进程是否在运行
            if process.poll() is None:
                # 保存基本守护进程信息（状态为STARTING）
                info = DaemonInfo(
                    pid=process.pid,
                    status=DaemonStatus.STARTING,
                    start_time=time.time(),
                    socket_path=socket_path,  # 子进程启动后设置
                    data_dir=self.data_dir
                )
                self.save_daemon_info(info)

                self.logger.info(f"Daemon started with PID {process.pid}")
                return True
            else:
                stdout, stderr = process.communicate()
                self.logger.error(f"Daemon failed to start: {stderr.decode()}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to start daemon: {e}")
            return False

    def stop(self) -> bool:
        """停止守护进程"""
        info = self.get_daemon_info()
        if not info:
            self.logger.info("Daemon is not running")
            return True

        self.logger.info(f"Stopping daemon (PID {info.pid})...")

        try:
            # 检查进程是否存在
            try:
                os.kill(info.pid, 0)
                is_alive = True
            except OSError:
                is_alive = False

            if not is_alive:
                self.logger.info("Daemon process not found. Cleaning up...")
                return True

            # 终止进程
            if os.name == 'nt':
                # 在Windows上，使用taskkill更可靠
                subprocess.run(['taskkill', '/F', '/PID', str(info.pid)], check=True, capture_output=True)
            else:
                # 在Unix-like系统上，使用信号
                os.kill(info.pid, signal.SIGTERM)
                # 等待进程结束
                for _ in range(10):  # 等待最多5秒
                    time.sleep(0.5)
                    try:
                        os.kill(info.pid, 0)
                    except OSError:
                        break # 进程已结束
                else:
                    # 强制终止
                    os.kill(info.pid, signal.SIGKILL)
                    time.sleep(0.5)

            self.logger.info("Daemon stopped")
            return True

        except Exception as e:
            print("4")
            # 如果进程已经不存在，也算成功
            if isinstance(e, OSError) and e.errno == 3: # No such process
                 self.logger.warning(f"Daemon process with PID {info.pid} not found, but continuing cleanup.")
                 return True
            return False
        finally:
            if os.path.exists(self.info_file):
                try:
                    os.remove(self.info_file)
                    self.logger.info("Daemon info file removed.")
                except OSError as e:
                    self.logger.error(f"Failed to remove daemon info file: {e}")

    def status(self) -> Dict[str, Any]:
        """获取守护进程状态"""
        info = self.get_daemon_info()
        if not info:
            return {'running': False, 'message': 'Daemon is not running'}

        is_alive = False
        try:
            os.kill(info.pid, 0)
            is_alive = True
        except OSError:
            pass

        if is_alive:
            uptime = time.time() - info.start_time
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int(uptime % 60)

            return {
                'running': True,
                'pid': info.pid,
                'status': info.status.value,
                'uptime': f"{hours}h {minutes}m {seconds}s",
                'socket_path': info.socket_path,
                'data_dir': info.data_dir
            }
        else:
            # 清理过期的信息文件
            if os.path.exists(self.info_file):
                os.remove(self.info_file)
            return {'running': False, 'message': 'Daemon process not found'}

    def _get_socket_path(self) -> str:
        """获取IPC socket路径"""
        if sys.platform == 'win32':
            # Windows命名管道
            pipe_name = f'\\\\.\\pipe\\pmg-daemon-{os.getpid()}'
            return pipe_name
        else:
            # Unix Domain Socket
            socket_dir = tempfile.gettempdir()
            socket_name = f'pmg-daemon-{os.getpid()}.sock'
            return os.path.join(socket_dir, socket_name)


class DaemonMain:
    """守护进程主循环"""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir
        self.running = False
        self.logger = logging.getLogger(__name__)

    def run(self):
        """运行守护进程主循环"""
        self.running = True

        # 设置信号处理
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self.logger.info("Daemon main loop started")

        # 初始化管理器
        # TODO: 初始化SessionManager和CryptoManager

        # 主循环
        while self.running:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break

        self.logger.info("Daemon main loop stopped")

    def _handle_signal(self, signum, frame):
        """处理终止信号"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False