#!/usr/bin/env python3
"""
构建可执行文件
"""

import os
import sys
import subprocess
import shutil


def build_exe():
    """构建可执行文件"""
    print("Building PMG executable...")

    # 安装依赖
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 构建命令
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "pmg",
        "--hidden-import", "cryptography",
        "--hidden-import", "argon2",
        "--hidden-import", "argon2._ffi",
        "--hidden-import", "cryptography.hazmat.backends.openssl",
        "--hidden-import", "cryptography.hazmat.bindings.openssl",
        "--add-data", "pmg;pmg",  # 包含pmg包
        "pmg_main.py"
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Build failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

    print("\nBuild successful!")
    print(f"Executable: {os.path.abspath('dist/pmg')}")

    # 在Windows上显示正确的扩展名
    if sys.platform == "win32":
        exe_path = os.path.abspath("dist/pmg.exe")
        if os.path.exists(exe_path):
            print(f"Windows executable: {exe_path}")
        else:
            # 尝试重命名
            src = os.path.abspath("dist/pmg")
            dst = os.path.abspath("dist/pmg.exe")
            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"Renamed to: {dst}")

    return True


if __name__ == "__main__":
    try:
        success = build_exe()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)