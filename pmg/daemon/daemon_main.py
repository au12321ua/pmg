"""
守护进程主入口
"""

import os
import sys
import signal
import logging
import argparse

from .daemon import DaemonMain, DaemonManager, DaemonInfo, DaemonStatus
from ..utils.ipc import IPCServer, Message, MessageType
from ..utils.crypto import CryptoManager, MultipleUsernamesError


class DaemonCommandHandler:
    """守护进程命令处理器"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.password = None
        self.crypto_manager = CryptoManager(data_dir)

        self.logger = logging.getLogger(__name__)

    def _is_valid(self) -> bool:
        return self.crypto_manager.verify_master_password(self.password)

    def handle_message(self, message: Message) -> Message:
        """处理消息"""
        try:
            self.logger.debug(f"Handling message: {message.command}")

            if message.type != MessageType.REQUEST:
                return Message(
                    id=message.id,
                    type=MessageType.ERROR,
                    error="Invalid message type"
                )
            
            is_valid = self._is_valid()
            if message.command not in {'login', 'logout', 'status'}:
                if not is_valid:
                    return Message(
                        id=message.id,
                        type=MessageType.ERROR,
                        error=f"Permission error: {message.command}"
                    )

            # 处理命令
            handler = getattr(self, f"handle_{message.command}", None)
            if not handler:
                return Message(
                    id=message.id,
                    type=MessageType.ERROR,
                    error=f"Unknown command: {message.command}"
                )

            result = handler(message.args or {})
            return Message(
                id=message.id,
                type=MessageType.RESPONSE,
                data=result
            )

        except Exception as e:
            self.logger.error(f"Error handling command {message.command}: {e}")
            return Message(
                id=message.id,
                type=MessageType.ERROR,
                error=str(e)
            )

    def handle_login(self, args: dict) -> dict:
        """处理登录"""
        if self._is_valid():
            return {'success': False, 'error': 'Repeated login'}
        
        self.password = args.get('password')
        if not self.password:
            return {'success': False, 'error': 'Password required'}

        if not self.crypto_manager.verify_master_password(self.password):
            return {'success': False, 'error': 'Invalid password'}

        return {
            'success': True
        }

    def handle_status(self, args: dict) -> dict:
        """处理状态查询"""
        result = {'authenticated': self._is_valid()}

        return result

    def handle_add(self, args: dict) -> dict:
        """处理添加密码"""
        site = args.get('site')
        username = args.get('username')
        password = args.get('password')

        if not site or not username or not password:
            return {'success': False, 'error': 'Site, username and password required'}

        success = self.crypto_manager.add_entry(site, username, password)
        return {'success': success, 'site': site}

    def handle_get(self, args: dict) -> dict:
        """处理获取密码"""
        site = args.get('site')
        username = args.get('username')
        if not site:
            return {'success': False, 'error': 'Site required'}

        try:
            result = self.crypto_manager.get_entry(site, username)
        except MultipleUsernamesError as e:
            return {
                'success': False,
                'error': f"Multiple usernames found for site '{site}'",
                'site': site,
                'ambiguous': True,
                'candidates': e.usernames
            }

        if not result:
            if username:
                return {'success': False, 'error': f'Entry not found: {site}/{username}'}
            return {'success': False, 'error': f'Site not found: {site}'}

        selected_username, password = result
        return {
            'success': True,
            'site': site,
            'username': selected_username,
            'password': password
        }

    def handle_list(self, args: dict) -> dict:
        """处理列出站点"""
        entries = self.crypto_manager.list_entries()
        return {'success': True, 'entries': entries}

    def handle_delete(self, args: dict) -> dict:
        """处理删除站点"""
        site = args.get('site')
        username = args.get('username')
        if not site:
            return {'success': False, 'error': 'Site required'}

        try:
            success = self.crypto_manager.delete_entry(site, username)
        except MultipleUsernamesError as e:
            return {
                'success': False,
                'error': f"Multiple usernames found for site '{site}'",
                'site': site,
                'ambiguous': True,
                'candidates': e.usernames
            }

        if not success and username:
            return {'success': False, 'site': site, 'username': username, 'error': f'Entry not found: {site}/{username}'}

        return {'success': success, 'site': site, 'username': username}

    def handle_logout(self, args: dict) -> dict:
        """处理登出"""
        self.password = None
        return {'success': True}


    def handle_gen(self, args: dict) -> dict:
        """处理生成密码"""
        site = args.get('site')
        username = args.get('username')
        length = args.get('length', 16)

        if not site or not username:
            return {'success': False, 'error': 'Site and username required'}

        # 生成密码
        from ..utils.crypto import CryptoManager
        password = CryptoManager.generate_password(length)

        # 保存
        success = self.crypto_manager.add_entry(site, username, password)
        if success:
            return {'success': True, 'site': site, 'password': password}
        else:
            return {'success': False, 'error': f'Failed to save to {site}'}

    def export(self, filename: str) -> bool:
        """导出数据"""
        try:
            entries = self.crypto_manager._load_entries()
            if not entries:
                print("No data to export")
                return False

            # 解密所有密码
            decrypted_data = {}
            for site, site_entries in entries.items():
                decrypted_data[site] = {}
                for username, entry in site_entries.items():
                    password = self.crypto_manager._decrypt_password(entry['password'])
                    decrypted_data[site][username] = {
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
        try:
            import json
            with open(filename, 'r') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError('Import data must be an object with site keys')

            # 导入每个条目
            count = 0
            for site, site_entries in data.items():
                if not isinstance(site_entries, dict):
                    raise ValueError(f"Invalid site data for '{site}'")

                for username, entry in site_entries.items():
                    if not isinstance(entry, dict) or 'password' not in entry:
                        raise ValueError(f"Invalid entry format for '{site}/{username}'")
                    if self.crypto_manager.add_entry(site, username, entry['password']):
                        count += 1

            print(f"Imported {count} entries from {filename}")
            return True

        except Exception as e:
            print(f"Error: {e}")
            return False
    
    
    def handle_export(self, args: dict) -> dict:
        """处理导出数据"""
        filename = args.get('file')
        if not filename:
            return {'success': False, 'error': 'Filename required'}

        try:
            success = self.export(filename)
            return {'success': success}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_import(self, args: dict) -> dict:
        """处理导入数据"""
        filename = args.get('file')
        if not filename:
            return {'success': False, 'error': 'Filename required'}

        try:
            success = self.import_data(filename)
            return {'success': success}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def handle_change_password(self, args: dict) -> dict:
        """处理更改主密码"""
        current_password = args.get('current_password')
        new_password = args.get('new_password')
        confirm_password = args.get('confirm_password')

        if not current_password or not new_password or not confirm_password:
            return {'success': False, 'error': 'Current password, new password and confirmation required'}

        if new_password != confirm_password:
            return {'success': False, 'error': 'New passwords do not match'}

        if len(new_password) < 8:
            return {'success': False, 'error': 'New password must be at least 8 characters'}

        success = self.crypto_manager.change_master_password(current_password, new_password)
        return {'success': success}

    # 其他命令处理函数可以根据需要添加


def main():
    """守护进程主函数"""
    parser = argparse.ArgumentParser(description='PMG Daemon')
    parser.add_argument('--data-dir', help='Data directory')
    parser.add_argument('--socket-path', help='IPC socket path')
    parser.add_argument('--foreground', '-f', action='store_true',
                       help='Run in foreground (do not daemonize)')

    args = parser.parse_args()

    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(args.data_dir or '.', 'daemon.log')),
            logging.StreamHandler(sys.stderr)
        ]
    )

    logger = logging.getLogger(__name__)

    # 确定数据目录
    if args.data_dir:
        data_dir = args.data_dir
    else:
        if os.name == 'nt':  # Windows
            data_dir = os.path.join(os.environ.get('APPDATA', ''), '.pmg')
        else:  # Linux/macOS
            data_dir = os.path.join(os.path.expanduser('~'), '.pmg')

    os.makedirs(data_dir, exist_ok=True)

    logger.info(f"Starting PMG daemon with data directory: {data_dir}")

    # 初始化命令处理器
    handler = DaemonCommandHandler(data_dir)

    # 获取socket路径
    dm = DaemonManager(data_dir)
    socket_path = args.socket_path or dm._get_socket_path()

    # 创建IPC服务器
    ipc_server = IPCServer(socket_path, handler.handle_message)

    try:
        # 启动IPC服务器
        ipc_server.start()

        logger.info(f"IPC server listening on {socket_path}")

        # 保存守护进程信息
        import time
        info = DaemonInfo(
            pid=os.getpid(),
            status=DaemonStatus.RUNNING,
            start_time=time.time(),
            socket_path=socket_path,
            data_dir=data_dir
        )
        dm.save_daemon_info(info)

        logger.info("Daemon started successfully")

        # 主循环
        if args.foreground:
            logger.info("Running in foreground mode")
            try:
                while True:
                    signal.pause()
            except KeyboardInterrupt:
                logger.info("Received interrupt, shutting down...")
        else:
            # 守护进程模式
            daemon_main = DaemonMain(data_dir)
            daemon_main.run()

    except Exception as e:
        logger.error(f"Daemon error: {e}")
        sys.exit(1)
    finally:
        ipc_server.stop()
        logger.info("Daemon stopped")


if __name__ == '__main__':
    main()