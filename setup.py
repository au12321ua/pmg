"""
安装配置
"""

from setuptools import setup, find_packages

setup(
    name="pmg",
    version="1.0.0",
    description="Personal Password Manager",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "cryptography>=42.0.0",
        "argon2-cffi>=25.0.0",
    ],
    entry_points={
        "console_scripts": [
            "pmg=pmg.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Topic :: Security",
        "Topic :: Utilities",
    ],
    python_requires=">=3.9",
)