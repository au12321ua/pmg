"""
IPC通信模块
"""

import os
import sys
import json
import socket
import struct
import threading
import logging
import uuid
import time
from typing import Optional, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    NOTIFICATION = "notification"


@dataclass
class Message:
    """IPC消息"""
    id: str
    type: MessageType
    command: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    auth_token: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            'id': self.id,
            'type': self.type.value
        }

        if self.command:
            result['command'] = self.command
        if self.args:
            result['args'] = self.args
        if self.data:
            result['data'] = self.data
        if self.error:
            result['error'] = self.error
        if self.auth_token:
            result['auth_token'] = self.auth_token

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息"""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            type=MessageType(data['type']),
            command=data.get('command'),
            args=data.get('args'),
            data=data.get('data'),
            error=data.get('error'),
            auth_token=data.get('auth_token')
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """从JSON字符串创建消息"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class IPCError(Exception):
    """IPC错误"""
    pass


class IPCServer:
    """IPC服务器"""

    def __init__(self, socket_path: str, handler: Callable):
        """
        初始化IPC服务器

        Args:
            socket_path: socket路径（Unix socket或Windows命名管道）
            handler: 消息处理函数，接收Message对象，返回Message对象
        """
        self.socket_path = socket_path
        self.handler = handler
        self.server_socket = None
        self.running = False
        self.thread = None
        self.logger = logging.getLogger(__name__)

        # 客户端连接列表
        self.clients = []

    def start(self):
        """启动IPC服务器"""
        if self.running:
            self.logger.warning("IPC server is already running")
            return

        self.logger.info(f"Starting IPC server on {self.socket_path}")

        # 清理旧的socket文件（Unix）
        if sys.platform != 'win32' and os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        try:
            if sys.platform == 'win32':
                # Windows命名管道
                import win32pipe

                self.server_socket = win32pipe.CreateNamedPipe(
                    self.socket_path,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1,  # 最大实例数
                    65536,  # 输出缓冲区大小
                    65536,  # 输入缓冲区大小
                    0,  # 默认超时
                    None  # 安全属性
                )
                self.running = True
                self.thread = threading.Thread(target=self._win32_main_loop)
                self.thread.daemon = True
                self.thread.start()

            else:
                # Unix Domain Socket
                self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.server_socket.bind(self.socket_path)
                self.server_socket.listen(5)

                # 设置socket权限（仅限当前用户）
                os.chmod(self.socket_path, 0o600)

                self.running = True
                self.thread = threading.Thread(target=self._unix_main_loop)
                self.thread.daemon = True
                self.thread.start()

            self.logger.info("IPC server started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start IPC server: {e}")
            raise IPCError(f"Failed to start IPC server: {e}")

    def stop(self):
        """停止IPC服务器"""
        if not self.running:
            return

        self.logger.info("Stopping IPC server...")
        self.running = False

        # 关闭所有客户端连接
        for client in self.clients:
            try:
                client.close()
            except:
                pass

        # 关闭服务器socket
        if self.server_socket:
            try:
                if sys.platform == 'win32':
                    import win32file
                    win32file.CloseHandle(self.server_socket)
                else:
                    self.server_socket.close()

                    # 删除socket文件
                    if os.path.exists(self.socket_path):
                        os.remove(self.socket_path)
            except:
                pass

        if self.thread:
            self.thread.join(timeout=2)

        self.logger.info("IPC server stopped")

    def _unix_main_loop(self):
        """Unix socket主循环"""
        while self.running:
            try:
                # 设置超时以便可以检查running标志
                self.server_socket.settimeout(1.0)
                client_socket, client_address = self.server_socket.accept()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting connection: {e}")
                break

            if client_socket:
                # 在新线程中处理客户端
                client_thread = threading.Thread(
                    target=self._handle_unix_client,
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()

    def _win32_main_loop(self):
        """Windows命名管道主循环"""
        import win32pipe
        import win32file
        import pywintypes

        while self.running:
            try:
                # 等待客户端连接
                win32pipe.ConnectNamedPipe(self.server_socket, None)

                # 处理客户端请求
                self._handle_win32_client(self.server_socket)

                # 断开连接
                win32pipe.DisconnectNamedPipe(self.server_socket)

            except pywintypes.error as e:
                if e.winerror == 232:  # 管道正在关闭
                    break
                elif self.running:
                    self.logger.error(f"Error in named pipe: {e}")
                    time.sleep(0.1)
                else:
                    break
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error in named pipe: {e}")
                    time.sleep(0.1)
                else:
                    break

    def _handle_unix_client(self, client_socket: socket.socket):
        """处理Unix socket客户端"""
        try:
            while self.running:
                # 读取消息长度
                header = client_socket.recv(4)
                if not header:
                    break

                msg_length = struct.unpack('!I', header)[0]

                # 读取消息内容
                data = b''
                while len(data) < msg_length:
                    chunk = client_socket.recv(min(4096, msg_length - len(data)))
                    if not chunk:
                        break
                    data += chunk

                if len(data) < msg_length:
                    break

                # 解析和处理消息
                try:
                    message = Message.from_json(data.decode('utf-8'))
                    response = self.handler(message)
                    response_data = response.to_json().encode('utf-8')

                    # 发送响应
                    response_header = struct.pack('!I', len(response_data))
                    client_socket.sendall(response_header + response_data)

                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
                    error_response = Message(
                        id=str(uuid.uuid4()),
                        type=MessageType.ERROR,
                        error=str(e)
                    )
                    error_data = error_response.to_json().encode('utf-8')
                    response_header = struct.pack('!I', len(error_data))
                    client_socket.sendall(response_header + error_data)

        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _handle_win32_client(self, pipe_handle):
        """处理Windows命名管道客户端"""
        import win32file
        import win32pipe
        import pywintypes

        try:
            while self.running:
                # 读取消息
                result, data = win32file.ReadFile(pipe_handle, 65536)
                if not data:
                    break

                # 解析和处理消息
                try:
                    message = Message.from_json(data.decode('utf-8'))
                    response = self.handler(message)
                    response_data = response.to_json().encode('utf-8')

                    # 发送响应
                    win32file.WriteFile(pipe_handle, response_data)

                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
                    error_response = Message(
                        id=str(uuid.uuid4()),
                        type=MessageType.ERROR,
                        error=str(e)
                    )
                    error_data = error_response.to_json().encode('utf-8')
                    win32file.WriteFile(pipe_handle, error_data)

        except pywintypes.error as e:
            if e.winerror == 109:  # ERROR_BROKEN_PIPE
                self.logger.debug("Pipe client disconnected.")
            else:
                self.logger.error(f"Error handling pipe client: {e}")
        except Exception as e:
            self.logger.error(f"Error handling pipe client: {e}")
        finally:
            pass


class IPCClient:
    """IPC客户端"""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.socket = None
        self.connected = False
        self.logger = logging.getLogger(__name__)

    def connect(self, timeout: float = 5.0) -> bool:
        """连接到IPC服务器"""
        if self.connected:
            return True

        self.logger.debug(f"Connecting to IPC server at {self.socket_path}")

        try:
            if sys.platform == 'win32':
                # Windows命名管道
                import win32pipe
                import win32file
                import pywintypes

                self.socket = win32file.CreateFile(
                    self.socket_path,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None
                )
                self.connected = True

            else:
                # Unix Domain Socket
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.settimeout(timeout)
                self.socket.connect(self.socket_path)
                self.connected = True

            self.logger.debug("Connected to IPC server")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to IPC server: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """断开连接"""
        if not self.connected:
            return

        try:
            if sys.platform == 'win32':
                import win32file
                win32file.CloseHandle(self.socket)
            else:
                self.socket.close()
        except:
            pass

        self.socket = None
        self.connected = False

    def send_message(self, message: Message, timeout: float = 10.0) -> Optional[Message]:
        """发送消息并等待响应"""
        if not self.connected:
            if not self.connect():
                return None

        try:
            message_data = message.to_json().encode('utf-8')

            if sys.platform == 'win32':
                import win32file
                import win32pipe

                # 发送消息
                win32file.WriteFile(self.socket, message_data)

                # 读取响应
                result, response_data = win32file.ReadFile(self.socket, 65536)
                if not response_data:
                    return None

                response = Message.from_json(response_data.decode('utf-8'))
                return response

            else:
                # 设置超时
                self.socket.settimeout(timeout)

                # 发送消息长度和内容
                header = struct.pack('!I', len(message_data))
                self.socket.sendall(header + message_data)

                # 接收响应
                header = self.socket.recv(4)
                if not header:
                    return None

                response_length = struct.unpack('!I', header)[0]

                data = b''
                while len(data) < response_length:
                    chunk = self.socket.recv(min(4096, response_length - len(data)))
                    if not chunk:
                        break
                    data += chunk

                if len(data) < response_length:
                    return None

                response = Message.from_json(data.decode('utf-8'))
                return response

        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            return None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()