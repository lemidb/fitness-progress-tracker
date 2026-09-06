import structlog

def get_logger(name: str = __name__):
    return structlog.get_logger(name)
