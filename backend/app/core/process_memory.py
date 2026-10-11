import os


def get_process_rss_mb() -> float:
    """Return current process resident set size (RSS / Working Set) in megabytes."""
    if os.name == "nt":
        import ctypes
        import ctypes.wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        try:
            psapi = ctypes.WinDLL("kernel32", use_last_error=True)
            fn = psapi.K32GetProcessMemoryInfo
            fn.argtypes = [
                ctypes.wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                ctypes.wintypes.DWORD,
            ]
            fn.restype = ctypes.wintypes.BOOL

            handle = psapi.GetCurrentProcess()
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if fn(handle, ctypes.byref(pmc), pmc.cb):
                return round(pmc.WorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass
        return 0.0
    else:
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            # On Linux ru_maxrss is in KB, on macOS in bytes
            factor = 1024 if os.uname().sysname != "Darwin" else (1024 * 1024)
            return round(usage.ru_maxrss / factor, 2)
        except Exception:
            return 0.0
