"""
命令行接口
"""

import argparse
import sys
import os

from .client.interactive_client import InteractivePMGClient


def get_data_dir() -> str:
    """获取数据目录"""
    if os.name == 'nt':  # Windows
        return os.path.join(os.environ.get('APPDATA', ''), '.pmg')
    else:  # Linux/macOS
        return os.path.join(os.path.expanduser('~'), '.pmg')


def main():
    parser = argparse.ArgumentParser(
        description="Personal Password Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pmg init                    # First time setup
  pmg login                   # Login with master password
  pmg add github myuser       # Add password for github
  pmg get github myuser       # Get password for github/myuser
  pmg gen google myuser       # Generate and save password
  pmg list                    # List all sites
  pmg status                  # Check login status
  pmg logout                  # Logout

Session Management:
  After login, a 6-digit session key will be generated. Use this key with other commands:
    pmg --session-key|-k 123456 get github myuser
        """
    )

    # 添加全局会话密钥参数
    parser.add_argument('--session-key', '-k', help='Session key for authentication')

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # init
    subparsers.add_parser('init', help='First time setup')

    # login
    subparsers.add_parser('login', help='Login with master password')

    # logout
    subparsers.add_parser('logout', help='Logout')

    # status
    subparsers.add_parser('status', help='Check login status')

    # add
    add_parser = subparsers.add_parser('add', help='Add password for a site')
    add_parser.add_argument('site', help='Site name')
    add_parser.add_argument('username', help='Username/email')

    # get
    get_parser = subparsers.add_parser('get', help='Get password for a site')
    get_parser.add_argument('site', help='Site name')
    get_parser.add_argument('username', nargs='?', help='Username/email (optional)')

    # list
    subparsers.add_parser('list', help='List all sites')

    # delete
    delete_parser = subparsers.add_parser('delete', help='Delete a site')
    delete_parser.add_argument('site', help='Site name')
    delete_parser.add_argument('username', nargs='?', help='Username/email (optional)')

    # gen
    gen_parser = subparsers.add_parser('gen', help='Generate and save password')
    gen_parser.add_argument('site', help='Site name')
    gen_parser.add_argument('username', help='Username/email')
    gen_parser.add_argument('-l', '--length', type=int, default=16,
                          help='Password length (default: 16)')

    # export
    export_parser = subparsers.add_parser('export', help='Export data to file')
    export_parser.add_argument('file', help='Output filename')

    # import
    import_parser = subparsers.add_parser('import', help='Import data from file')
    import_parser.add_argument('file', help='Input filename')

    # change-password
    subparsers.add_parser('change-password', help='Change master password')


    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # 处理命令
    try:
        client = InteractivePMGClient()

        if args.command == 'init':
            success = client.interactive_init()

        elif args.command == 'login':
            success = client.interactive_login()

        elif args.command == 'logout':
            success = client.logout()

        elif args.command == 'status':
            success = client.interactive_status()

        elif args.command == 'add':
            success = client.interactive_add(args.site, args.username)

        elif args.command == 'get':
            success = client.interactive_get(args.site, args.username)

        elif args.command == 'list':
            success = client.interactive_list()

        elif args.command == 'delete':
            success = client.interactive_delete(args.site, args.username)

        elif args.command == 'gen':
            success = client.interactive_gen(args.site, args.username, args.length)

        elif args.command == 'export':
            success = client.export(args.file)

        elif args.command == 'import':
            success = client.import_data(args.file)

        elif args.command == 'change-password':
            success = client.change_password()

        else:
            parser.print_help()
            success = False

        client.close()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print("flag")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()