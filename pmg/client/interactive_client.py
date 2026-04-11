"""
用户友好的client CLI界面模块
"""
import getpass
from typing import Optional

from .client import PMGClient

class InteractivePMGClient(PMGClient):
    """交互式客户端，提供更友好的用户交互"""

    def interactive_init(self) -> bool:
        """交互式初始化"""
        print("First time setup")
        print("Set your master password (remember it, it cannot be recovered)")
        password = getpass.getpass("Master password: ")
        confirm = getpass.getpass("Confirm master password: ")
        return self.init(password, confirm)
    
    def interactive_login(self) -> bool:
        """交互式登录"""
        print("Login to PMG")
        password = getpass.getpass("Master password: ")
        return self.login(password)
    
    def interactive_status(self) -> bool:
        """交互式状态查询"""
        status_result = self.status()
        if 'authenticated' in status_result:
            if status_result['authenticated']:
                print("Authenticated")
            else:
                print("Not authenticated, login first")
        else:
            print("Status check failed")
        return True

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
    
    def interactive_get(self, site: str, username: str) -> bool:
        """交互式获取密码"""
        result = self.get(site, username)
        if result and result.get('ambiguous'):
            candidates = result.get('candidates', [])
            print(f"Multiple usernames found for '{site}':")
            for idx, username in enumerate(candidates, start=1):
                print(f"  {idx}. {username}")

            choice = input("Select username number: ").strip()
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(candidates):
                print("Error: Invalid selection")
                return False
            else:
                selected_username = candidates[int(choice) - 1]
                result = self.get(site, selected_username)

        if result and not result.get('ambiguous'):
            print(f"Site: {result['site']}")
            print(f"Username: {result['username']}")
            print(f"Password: {result['password']}")
            return True
        else:
            if username:
                print(f"Error: Entry '{site}/{username}' not found")
            else:
                print(f"Error: Site '{site}' not found")
            return False

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
    
    def interactive_list(self) -> bool:
        """交互式list"""
        entries = self.list()
        if entries:
            print("Saved sites:")
            for site, usernames in entries.items():
                print(f"  {site}:")
                for username in usernames:
                    print(f"    - {username}")
        else:
            print("No entries found")
        return True
    
    def interactive_delete(self, site: str, username: Optional[str] = None) -> bool:
        """交互式删除密码"""
        selected_username = username

        if not selected_username:
            entries = self.list()
            usernames = entries.get(site, [])
            if not usernames:
                print(f"Error: Site '{site}' not found")
                return False
            elif len(usernames) == 1:
                selected_username = usernames[0]
            else:
                print(f"Multiple usernames found for '{site}':")
                for idx, username in enumerate(usernames, start=1):
                    print(f"  {idx}. {username}")
                choice = input("Select username number: ").strip()
                if not choice.isdigit() or int(choice) < 1 or int(choice) > len(usernames):
                    print("Error: Invalid selection")
                    return False
                else:
                    selected_username = usernames[int(choice) - 1]
        
        target = f"{site}/{selected_username}"
        confirm = input(f"Delete '{target}'? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return True
        else:
            result = self.delete(site, selected_username)
            if result.get('success'):
                return True
            if result.get('ambiguous'):
                print(f"Error: Multiple usernames found for '{site}'")
                return False
            if result.get('error'):
                print(f"Error: {result['error']}")
            return False