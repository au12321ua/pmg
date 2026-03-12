#!/usr/bin/env python3
"""
测试PMG功能
"""

import os
import sys
import tempfile
import shutil
from pmg.core import PasswordManagerCore


def test_basic():
    """基本功能测试"""
    print("Testing PMG basic functionality...")

    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 修改数据目录
        original_core = PasswordManagerCore
        class TestPasswordManagerCore(original_core):
            def __init__(self):
                self.data_dir = tmpdir
                from pmg.crypto import CryptoManager
                from pmg.session import SessionManager
                self.crypto = CryptoManager(self.data_dir)
                self.session = SessionManager(self.data_dir)

        pm = TestPasswordManagerCore()

        # 测试1: 初始化
        print("\n1. Testing init...")
        # 模拟用户输入
        import io
        import getpass

        # 保存原始getpass
        original_getpass = getpass.getpass

        test_inputs = ["testpassword123", "testpassword123"]
        input_index = [0]

        def mock_getpass(prompt=""):
            if input_index[0] < len(test_inputs):
                value = test_inputs[input_index[0]]
                input_index[0] += 1
                print(prompt + "[TEST_PASSWORD]")
                return value
            return original_getpass(prompt)

        getpass.getpass = mock_getpass

        try:
            if pm.init():
                print("[OK] Init successful")
            else:
                print("[FAIL] Init failed")
                return False
        finally:
            getpass.getpass = original_getpass

        # 测试2: 登录
        print("\n2. Testing login...")
        if pm.login("testpassword123"):
            print("[OK] Login successful")
        else:
            print("[FAIL] Login failed")
            return False

        if not pm.login("wrongpassword"):
            print("[OK] Wrong password rejected")
        else:
            print("[FAIL] Wrong password accepted")
            return False

        # 测试3: 状态
        print("\n3. Testing status...")
        if pm.status():
            print("[OK] Status shows authenticated")
        else:
            print("[FAIL] Status failed")
            return False

        # 测试4: 添加密码
        print("\n4. Testing add...")
        # 模拟密码输入
        original_getpass = getpass.getpass
        def mock_getpass_add(prompt=""):
            print(prompt + "[TestPass123!]")
            return "TestPass123!"

        getpass.getpass = mock_getpass_add
        try:
            if pm.add("github", "test@example.com"):
                print("[OK] Add successful")
            else:
                print("[FAIL] Add failed")
                return False
        finally:
            getpass.getpass = original_getpass

        # 测试5: 列出
        print("\n5. Testing list...")
        if pm.list():
            print("[OK] List successful")
        else:
            print("[FAIL] List failed")
            return False

        # 测试6: 获取
        print("\n6. Testing get...")
        if pm.get("github"):
            print("[OK] Get successful")
        else:
            print("[FAIL] Get failed")
            return False

        # 测试7: 生成密码
        print("\n7. Testing gen...")
        if pm.gen("google", "test@example.com", 12):
            print("[OK] Gen successful")
        else:
            print("[FAIL] Gen failed")
            return False

        # 测试8: 登出
        print("\n8. Testing logout...")
        if pm.logout():
            print("[OK] Logout successful")
        else:
            print("[FAIL] Logout failed")
            return False

        # 测试9: 状态（登出后）
        print("\n9. Testing status after logout...")
        if not pm.status():
            print("[OK] Status shows not authenticated")
        else:
            print("[FAIL] Status should show not authenticated")
            return False

        print("\n" + "="*50)
        print("All tests passed!")
        print("="*50)
        return True


if __name__ == "__main__":
    try:
        success = test_basic()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nTest error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)