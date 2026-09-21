import signal
import sys

try:
    from pytest_cov.embed import cleanup as pytest_cov_cleanup
except ImportError:  # pragma: no cover
    # pytest-cov >= 7 no longer ships pytest_cov.embed
    pytest_cov_cleanup = None


def cleanup(*args, **kwargs):  # pragma: no cover
    # see https://github.com/pytest-dev/pytest-cov/issues/139
    if pytest_cov_cleanup is not None:
        pytest_cov_cleanup()
    sys.exit(1)


signal.signal(signal.SIGTERM, cleanup)
