import hupper
import os
import sys
import time

here = os.path.dirname(__file__)


def main():
    response_path = sys.argv[-1]
    if '--reload' in sys.argv:
        reloader = hupper.start_reloader('tests.myapp.__main__.main')

    if hupper.is_active():
        reloader.watch_files([os.path.join(here, 'foo.ini')])

    with open(response_path, 'ab') as fp:
        fp.write('{:d}\n'.format(int(time.time())).encode('utf8'))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
