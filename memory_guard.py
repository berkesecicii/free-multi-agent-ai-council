"""One heavy local inference process at a time."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import time

@contextmanager
def model_memory_lock(directory,cancelled=None,timeout=30):
    path=Path(directory)/'model-memory.lock';path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as handle:
        deadline=time.monotonic()+timeout
        while True:
            if cancelled is not None and cancelled.is_set():raise ValueError('Yerel işlem durduruldu.')
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline:raise ValueError('Diğer yerel ses/model işlemi sürüyor. Biraz sonra tekrar dene.')
                time.sleep(.1)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)
