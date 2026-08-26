import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("125.132.13.175", port=58020, username="u0_a172", password="12345678", timeout=15)

commands = [
    "mkdir -p /data/data/com.termux/files/home/test_clone && cd /data/data/com.termux/files/home/test_clone && rm -rf * .git",
    "cd /data/data/com.termux/files/home/test_clone && git init && git remote add origin https://github.com/ggerganov/llama.cpp.git && git fetch --depth=1 origin 5e6a37cb115dc1074e274ac004373f5661909695 && git checkout FETCH_HEAD",
    "cd /data/data/com.termux/files/home/test_clone && git rev-parse HEAD",
]

for cmd in commands:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(f"Exit code: {code}")
    if out:
        print(out.strip())
    if err:
        print(err.strip())

client.close()
