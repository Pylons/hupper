import sys
from .cli import main

sys.exit(main(sys.argv[1:]) or 0)
