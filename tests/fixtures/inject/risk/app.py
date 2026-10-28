import os
import pickle
import yaml


def load(blob):
    return pickle.loads(blob)          # CWE-502: arbitrary object construction


def run(expr):
    return eval(expr)                  # CWE-95: code injection


def cfg(text):
    return yaml.load(text)             # CWE-502: full loader, not SafeLoader


def ping(host):
    os.system(f"ping -c1 {host}")      # CWE-78: command built from input
