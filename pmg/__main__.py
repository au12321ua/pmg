"""
主入口点
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pmg.cli import main

if __name__ == "__main__":
    main()