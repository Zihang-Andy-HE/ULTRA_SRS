"""Portable process locks and runtime selection (no platform imports at import time)."""
import os
from contextlib import contextmanager


@contextmanager
def stage_lock(path):
    with open(path, 'a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('Output is already locked by another process') from exc
            try:
                yield
            finally:
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def peak_rss_kib():
    if os.name == 'nt':
        import psutil
        info = psutil.Process().memory_info()
        return getattr(info, 'peak_wset', info.rss) // 1024
    import resource, sys
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value // 1024 if sys.platform == 'darwin' else value


def resolve_device(device='auto'):
    import torch
    if device == 'auto':
        return 'cuda:0' if torch.cuda.is_available() else 'cpu'
    if device.startswith('cuda') and not torch.cuda.is_available():
        raise ValueError('CUDA is unavailable. Choose --device cpu or --device auto.')
    if device != 'cpu' and not device.startswith('cuda'):
        raise ValueError('Supported devices: auto, cpu, cuda:N')
    return device
