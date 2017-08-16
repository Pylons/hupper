import importlib


def resolve_spec(spec):
    modname, funcname = spec.rsplit('.', 1)
    module = importlib.import_module(modname)
    func = getattr(module, funcname)
    return func


def is_watchdog_supported():
    """ Return ``True`` if watchdog is available."""
    try:
        import watchdog  # noqa: F401
    except ImportError:
        return False
    return True
