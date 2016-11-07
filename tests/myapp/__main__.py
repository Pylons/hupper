from __future__ import print_function

import hupper
import os
import sys
import time

here = os.path.dirname(__file__)

def main():
    if '--reload' in sys.argv:
        reloader = hupper.start_reloader('tests.myapp.__main__.main')

    if hupper.is_active():
        reloader.watch_files([os.path.join(here, 'foo.ini')])

    print('myapp started')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    main()
