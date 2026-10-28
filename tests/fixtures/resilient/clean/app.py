import logging

log = logging.getLogger(__name__)


def read_config(path):
    """A narrow catch that logs and re-raises - it never swallows the failure."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        log.warning("config missing at %s", path)
        raise


def parse_port(value, default=8080):
    try:
        return int(value)
    except ValueError:
        log.warning("bad port %r, using %d", value, default)
        return default
