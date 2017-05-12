import pytest_cov.embed
import signal
import sys

def cleanup(*args, **kwargs):  # pragma: no cover
    # see https://github.com/pytest-dev/pytest-cov/issues/139
    pytest_cov.embed.cleanup()
    sys.exit(1)
signal.signal(signal.SIGTERM, cleanup)
