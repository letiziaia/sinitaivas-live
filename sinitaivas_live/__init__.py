# filepath: sinitaivas_live/__init__.py
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError  # type: ignore

try:
    __version__ = version("sinitaivas-live")
except PackageNotFoundError:
    # probably running from source, not installed
    __version__ = "dev"
