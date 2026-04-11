# PMG 使用说明

## 安装

### 方法1: 安装为Python包
```bash
# 在项目目录中
pip install -e .
```

安装后可以直接使用 `pmg` 命令。

### 方法2: 直接运行Python脚本
```bash
python -m pmg.cli <command>
```

或
```bash
python pmg_main.py <command>
```

### 方法3: 构建可执行文件
```bash
python build_exe.py
```
生成的可执行文件在 `dist/pmg.exe` (Windows) 或 `dist/pmg` (Linux/macOS)。

## 快速开始

### 1. 首次使用
```bash
pmg init
```
按照提示设置主密码（至少8位字符）。

### 2. 登录
```bash
pmg login <your_master_password>
```
登录后会话有效期为1小时。

### 3. 添加密码
```bash
pmg add <site_name> <username>
```
例如：
```bash
pmg add github your_email@example.com
```
系统会提示输入密码。

### 4. 获取密码
```bash
pmg get <site_name> [username]
```
例如：
```bash
pmg get github your_email@example.com
```

如果同一站点下有多个用户名，未提供 `username` 时会提示你选择。

### 5. 生成密码
```bash
pmg gen <site_name> <username> [--length 16]
```
例如：
```bash
pmg gen google your_email@example.com --length 20
```

### 6. 查看所有站点
```bash
pmg list
```

### 7. 检查登录状态
```bash
pmg status
```

### 8. 登出
```bash
pmg logout
```

## 完整命令参考

```
pmg init                    # 首次设置
pmg login <password>        # 登录
pmg logout                  # 登出
pmg status                  # 查看状态
pmg add <site> <username>   # 添加密码
pmg get <site> [username]   # 获取密码
pmg list                    # 按站点列出所有用户名
pmg delete <site> [username]# 删除指定站点用户名
pmg gen <site> <username>   # 生成并保存密码
pmg export <file>           # 导出数据
pmg import <file>           # 导入数据
pmg change-password         # 更改主密码
```

## 数据存储位置

- **Windows**: `%APPDATA%\.pmg\`
- **Linux/macOS**: `~/.pmg/`

文件：
- `config.json` - 配置和主密码哈希
- `data.enc` - 加密的密码数据库
- `session.token` - 会话令牌（1小时有效期）

## 安全说明

1. **主密码**：使用Argon2id算法哈希存储，无法恢复
2. **数据加密**：所有密码使用AES-GCM加密
3. **会话管理**：登录后1小时自动过期
4. **密钥派生**：每个密码使用独立的密钥

## 故障排除

### 1. 忘记主密码
无法恢复，需要删除 `~/.pmg/` 目录重新初始化。

### 2. 会话过期
重新登录：
```bash
pmg login <your_password>
```

### 3. 导入/导出警告
导出文件包含明文密码，请妥善保管。

### 4. 构建可执行文件问题
如果遇到OpenSSL错误，可以设置环境变量：
```bash
set CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1
python build_exe.py
```

## 示例工作流

```bash
# 首次使用
pmg init
# 设置主密码: MySecurePass123!

# 日常使用
pmg login MySecurePass123!
pmg add github myname@example.com
# 输入密码: GithubPass123!

pmg gen google myname@gmail.com --length 20
pmg get github
pmg list
pmg status
pmg logout
```

## 从其他管理器迁移

1. 从其他管理器导出为JSON格式：
```json
{
  "github": {
    "your_email@example.com": {
      "password": "your_password"
    },
    "work_email@example.com": {
      "password": "your_work_password"
    }
  }
}
```

2. 使用PMG导入：
```bash
pmg login <your_password>
pmg import exported_data.json
```