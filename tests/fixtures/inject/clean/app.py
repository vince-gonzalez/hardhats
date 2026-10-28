import json
import subprocess

import yaml


def load(blob):
    return json.loads(blob)


def cfg(text):
    return yaml.safe_load(text)


def ping(host):
    return subprocess.run(["ping", "-c1", host], check=True)
