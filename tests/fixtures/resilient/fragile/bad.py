import os, requests, subprocess
def f():
    try:
        risky()
    except:
        pass
def g():
    try:
        risky()
    except Exception:
        pass
def h():
    try:
        risky()
    except (ValueError,):
        pass
r = requests.get("http://x")
os.system("echo x")
subprocess.run(["ls"])
# TODO: fix this later
