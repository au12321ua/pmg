# PMG - Personal Password Manager

A secure command-line password manager with session-based authentication.

## Features

- 🔐 **Session-based authentication** (1-hour expiry)
- 🔒 **AES-GCM encryption** for all data
- 🔑 **Argon2id** for master password hashing
- 📝 **Simple CLI interface** with intuitive commands
- 🔧 **Password generation** with customizable length
- 🔄 **Master password change** with data re-encryption
- 📤 **Import/export** functionality

## Installation

### From source
```bash
git clone <repository>
cd pmg
pip install -e .
```

### Dependencies
```bash
pip install cryptography argon2-cffi
```

## Usage

### First time setup
```bash
pmg init
```

### Basic workflow
```bash
# Login
pmg login

# Add a password
pmg add github your_email@example.com

# Add another account under same site
pmg add github your_work_email@example.com

# Get a password
pmg get github your_email@example.com

# Generate and save a password
pmg gen google your_email@example.com

# List all sites
pmg list

# Check login status
pmg status

# Logout
pmg logout
```

### All commands
```
pmg init                    # First time setup
pmg login <password>        # Login with master password
pmg logout                  # Logout
pmg status                  # Check login status
pmg add <site> <username>   # Add password for a site
pmg get <site> [username]   # Get password for a site/user
pmg list                    # List all sites and usernames
pmg delete <site> [username]# Delete a site/user
pmg gen <site> <username>   # Generate and save password
pmg export <file>           # Export data to file
pmg import <file>           # Import data from file
pmg change-password         # Change master password
```

## Storage model

Passwords are stored by `site + username`:

```json
{
	"site-1": {
		"username-1": {
			"password": "...",
			"created_at": "...",
			"updated_at": "..."
		}
	}
}
```

When `get` or `delete` is called with only `site` and multiple usernames exist, PMG will ask you to choose a username.

## Security

- **Master password**: Hashed with Argon2id (time=3, memory=64MB)
- **Data encryption**: AES-GCM with 256-bit keys
- **Session tokens**: HMAC-SHA256 signed, 1-hour expiry
- **Password storage**: Each password individually encrypted
- **Key derivation**: Scrypt for master key, HMAC-SHA256 for password keys

## File locations

- **Windows**: `%APPDATA%\.pmg\`
- **Linux/macOS**: `~/.pmg/`

Files:
- `config.json` - Configuration and master password hash
- `data.enc` - Encrypted password database
- `session.token` - Session token (encrypted)

## Building executable

```bash
pip install pyinstaller
pyinstaller --onefile --name pmg pmg/cli.py
```

## License

MIT