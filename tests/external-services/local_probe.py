"""Bounded retries for read-only local host/container observations."""
import subprocess
import time


def read(command, *, input=None, text=False):
    """Never interpret a transient probe timeout as a successful health check."""
    for attempt in range(3):
        try:
            return subprocess.run(command,input=input,text=text,check=True,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError):
            if attempt==2:raise RuntimeError('Local read-only probe failed after three bounded attempts; output suppressed') from None
            time.sleep(.2)
