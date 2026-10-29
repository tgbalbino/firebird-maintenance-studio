"""Native (C/C++) call stack of another thread of this process, Windows x64 only.

faulthandler only sees Python frames.  When the UI thread is stuck inside Qt the
Python stack ends at `app.exec()`, so the cause has to come from the native one.
Names come from each DLL's export table (Qt exports its public methods).
"""

from __future__ import annotations

import sys

MAX_FRAMES = 40
_CONTEXT_SIZE = 1232  # sizeof(CONTEXT) on AMD64
_CONTEXT_FULL = 0x10000B
_RIP, _RSP, _RBP = 0xF8, 0x98, 0xA0


def capture_thread_stack(native_thread_id: int) -> list[str]:
    """Return 'module!symbol+0xoffset' lines for the thread, or [] where unsupported."""
    if sys.platform != "win32":
        return []
    try:
        return _capture(native_thread_id)
    except Exception as exc:  # a diagnostic must never take the app down
        return [f"(falha ao ler a pilha nativa: {exc})"]


def _capture(thread_id: int) -> list[str]:
    import ctypes
    import struct
    from ctypes import wintypes

    if struct.calcsize("P") != 8:
        return []

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    u64, handle = ctypes.c_uint64, ctypes.c_void_p

    kernel32.OpenThread.restype = handle
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.SuspendThread.argtypes = [handle]
    kernel32.SuspendThread.restype = wintypes.DWORD
    kernel32.ResumeThread.argtypes = [handle]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.GetThreadContext.argtypes = [handle, ctypes.c_void_p]
    kernel32.GetCurrentProcess.restype = handle
    kernel32.CloseHandle.argtypes = [handle]
    kernel32.GetModuleHandleExW.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(handle)]
    kernel32.GetModuleFileNameW.argtypes = [handle, wintypes.LPWSTR, wintypes.DWORD]

    class Address(ctypes.Structure):
        _fields_ = [("Offset", u64), ("Segment", ctypes.c_uint16), ("Mode", ctypes.c_uint32)]

    class StackFrame(ctypes.Structure):
        _fields_ = [
            ("AddrPC", Address), ("AddrReturn", Address), ("AddrFrame", Address),
            ("AddrStack", Address), ("AddrBStore", Address),
            ("FuncTableEntry", ctypes.c_void_p), ("Params", u64 * 4),
            ("Far", wintypes.BOOL), ("Virtual", wintypes.BOOL), ("Reserved", u64 * 3),
            ("KdHelp", ctypes.c_ubyte * 0x100),
        ]

    class SymbolInfo(ctypes.Structure):
        _fields_ = [
            ("SizeOfStruct", ctypes.c_uint32), ("TypeIndex", ctypes.c_uint32), ("Reserved", u64 * 2),
            ("Index", ctypes.c_uint32), ("Size", ctypes.c_uint32), ("ModBase", u64),
            ("Flags", ctypes.c_uint32), ("Value", u64), ("Address", u64),
            ("Register", ctypes.c_uint32), ("Scope", ctypes.c_uint32), ("Tag", ctypes.c_uint32),
            ("NameLen", ctypes.c_uint32), ("MaxNameLen", ctypes.c_uint32), ("Name", ctypes.c_char * 256),
        ]

    process = kernel32.GetCurrentProcess()
    dbghelp.SymSetOptions.argtypes = [wintypes.DWORD]
    dbghelp.SymSetOptions(0x2 | 0x4)  # SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS
    dbghelp.SymInitialize.argtypes = [handle, ctypes.c_char_p, wintypes.BOOL]
    dbghelp.SymRefreshModuleList.argtypes = [handle]
    if not dbghelp.SymInitialize(process, None, True):
        dbghelp.SymRefreshModuleList(process)
    dbghelp.SymFromAddr.argtypes = [handle, u64, ctypes.POINTER(u64), ctypes.POINTER(SymbolInfo)]
    dbghelp.SymFunctionTableAccess64.argtypes = [handle, u64]
    dbghelp.SymFunctionTableAccess64.restype = ctypes.c_void_p
    dbghelp.SymGetModuleBase64.argtypes = [handle, u64]
    dbghelp.SymGetModuleBase64.restype = u64
    dbghelp.StackWalk64.argtypes = [
        wintypes.DWORD, handle, handle, ctypes.POINTER(StackFrame), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ]
    function_table = ctypes.cast(dbghelp.SymFunctionTableAccess64, ctypes.c_void_p).value
    module_base = ctypes.cast(dbghelp.SymGetModuleBase64, ctypes.c_void_p).value

    def describe(address: int) -> str:
        module = handle()
        name = ""
        if kernel32.GetModuleHandleExW(0x4 | 0x2, address, ctypes.byref(module)):  # FROM_ADDRESS | UNCHANGED_REFCOUNT
            buffer = ctypes.create_unicode_buffer(520)
            kernel32.GetModuleFileNameW(module, buffer, 520)
            name = buffer.value.rsplit("\\", 1)[-1]
        symbol = SymbolInfo()
        symbol.SizeOfStruct = 88
        symbol.MaxNameLen = 255
        displacement = u64(0)
        if dbghelp.SymFromAddr(process, address, ctypes.byref(displacement), ctypes.byref(symbol)):
            return f"{name or '?'}!{symbol.Name.decode('ascii', 'replace')}+0x{displacement.value:x}"
        base = module.value or 0
        return f"{name or '?'}+0x{address - base:x}" if base else f"0x{address:x}"

    thread = kernel32.OpenThread(0x1FFFFF, False, thread_id)
    if not thread:
        return [f"(não abriu a thread {thread_id})"]
    lines: list[str] = []
    try:
        if kernel32.SuspendThread(thread) == 0xFFFFFFFF:
            return ["(não suspendeu a thread)"]
        try:
            raw = ctypes.create_string_buffer(_CONTEXT_SIZE + 16)
            start = (ctypes.addressof(raw) + 15) & ~15  # CONTEXT must be 16-byte aligned
            ctypes.c_uint32.from_address(start + 0x30).value = _CONTEXT_FULL
            if not kernel32.GetThreadContext(thread, ctypes.c_void_p(start)):
                return ["(não leu o contexto da thread)"]
            frame = StackFrame()
            for address, offset in ((frame.AddrPC, _RIP), (frame.AddrFrame, _RBP), (frame.AddrStack, _RSP)):
                address.Offset = u64.from_address(start + offset).value
                address.Mode = 3  # AddrModeFlat
            for _ in range(MAX_FRAMES):
                if not dbghelp.StackWalk64(0x8664, process, thread, ctypes.byref(frame), ctypes.c_void_p(start),
                                           None, function_table, module_base, None):
                    break
                if frame.AddrPC.Offset == 0:
                    break
                lines.append(describe(frame.AddrPC.Offset))
        finally:
            kernel32.ResumeThread(thread)
    finally:
        kernel32.CloseHandle(thread)
    return lines
