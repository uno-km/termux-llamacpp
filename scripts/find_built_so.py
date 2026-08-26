import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("125.132.13.175", port=58020, username="u0_a172", password="12345678", timeout=15)

commands = [
    "find /data/data/com.termux/files/usr/tmp/ -name '*.so*' 2>/dev/null",
    "find $HOME/termux-llamacpp -name '*.so*' 2>/dev/null",
    "ls -la $HOME/.termux-llama/bin",
]

for cmd in commands:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out.strip())
    if err:
        print("[STDERR]", err.strip())

client.close()
