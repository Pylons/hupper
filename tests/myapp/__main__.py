import sys
from .cli import main


from hupper.compat import PY64, OS64
print('PY64=%s\nOS64=%s' % (PY64, OS64))
sys.exit(main(sys.argv[1:]) or 0)
