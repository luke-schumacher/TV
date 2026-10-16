"""PyInstaller entry: importing the CLI keeps relative imports intact."""
import sys
from nostalgiabox.__main__ import main
if __name__ == '__main__':
    raise SystemExit(main(['--desktop', *sys.argv[1:]]))
