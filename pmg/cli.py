"""
命令行接口
"""

import argparse
import sys
from .core import PasswordManagerCore


def main():
    parser = argparse.ArgumentParser(
        description="Personal Password Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pmg init                    # First time setup
  pmg login mypassword        # Login with master password
  pmg add github myuser       # Add password for github
  pmg get github              # Get password for github
  pmg gen google myuser       # Generate and save password
  pmg list                    # List all sites
  pmg status                  # Check login status
  pmg logout                  # Logout
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # init
    subparsers.add_parser('init', help='First time setup')

    # login
    login_parser = subparsers.add_parser('login', help='Login with master password')
    login_parser.add_argument('password', help='Master password')

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

    # list
    subparsers.add_parser('list', help='List all sites')

    # delete
    delete_parser = subparsers.add_parser('delete', help='Delete a site')
    delete_parser.add_argument('site', help='Site name')

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

    # 创建核心实例
    pm = PasswordManagerCore()

    # 处理命令
    try:
        if args.command == 'init':
            success = pm.init()
        elif args.command == 'login':
            success = pm.login(args.password)
        elif args.command == 'logout':
            success = pm.logout()
        elif args.command == 'status':
            success = pm.status()
        elif args.command == 'add':
            success = pm.add(args.site, args.username)
        elif args.command == 'get':
            success = pm.get(args.site)
        elif args.command == 'list':
            success = pm.list()
        elif args.command == 'delete':
            success = pm.delete(args.site)
        elif args.command == 'gen':
            success = pm.gen(args.site, args.username, args.length)
        elif args.command == 'export':
            success = pm.export(args.file)
        elif args.command == 'import':
            success = pm.import_data(args.file)
        elif args.command == 'change-password':
            success = pm.change_password()
        else:
            parser.print_help()
            success = False

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()