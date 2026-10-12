import ctypes
import os

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('ExitStatus', ctypes.c_ulonglong),
        ('PebBaseAddress', ctypes.c_void_p),
        ('AffinityMask', ctypes.c_ulonglong),
        ('BasePriority', ctypes.c_ulonglong),
        ('UniqueProcessId', ctypes.c_ulonglong),
        ('InheritedFromUniqueProcessId', ctypes.c_ulonglong),
    ]

def main():
    hProc = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, 5420)
    pbi = PROCESS_BASIC_INFORMATION()
    ret_len = ctypes.c_ulong()
    ntdll.NtQueryInformationProcess(hProc, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(ret_len))

    proc_params_ptr = ctypes.c_void_p()
    kernel32.ReadProcessMemory(hProc, ctypes.c_void_p(pbi.PebBaseAddress + 0x20), ctypes.byref(proc_params_ptr), 8, None)

    env_ptr = ctypes.c_void_p()
    kernel32.ReadProcessMemory(hProc, ctypes.c_void_p(proc_params_ptr.value + 0x80), ctypes.byref(env_ptr), 8, None)

    buf = ctypes.create_string_buffer(65536)
    kernel32.ReadProcessMemory(hProc, env_ptr, buf, 65536, None)
    kernel32.CloseHandle(hProc)

    raw = buf.raw.decode('utf-16le', errors='ignore')
    env_vars = dict(s.split('=', 1) for s in raw.split('\x00') if '=' in s and not s.startswith('='))

    env_file = os.path.join(os.path.dirname(__file__), '..', 'backend', '.env')
    with open(env_file, 'r', encoding='utf-8') as f:
        existing = f.read()

    to_add = []
    keys = ['GROQ_API_KEY', 'OPENROUTER_API_KEY', 'HUGGINGFACE_API_KEY', 'GROQ_MODEL', 'OPENROUTER_MODEL', 'HUGGINGFACE_MODEL']
    for k in keys:
        if k in env_vars and k not in existing:
            to_add.append(f'{k}="{env_vars[k]}"')

    if to_add:
        with open(env_file, 'a', encoding='utf-8') as f:
            f.write('\n# Multi-provider keys\n' + '\n'.join(to_add) + '\n')
        print(f'Appended {len(to_add)} keys to {env_file}')
    else:
        print('All keys already present or none found')

if __name__ == '__main__':
    main()
