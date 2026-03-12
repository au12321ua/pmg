#!/usr/bin/env python3
"""
PMG主入口脚本
"""

import sys
import os

# 添加pmg包到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pmg.cli import main

if __name__ == "__main__":
    main()