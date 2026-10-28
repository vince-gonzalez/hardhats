import os


def client():
    """The credential is read from the environment, never written in the source."""
    token = os.environ["SERVICE_TOKEN"]
    return token
