import socket
import sys
import paramiko

def probe_and_connect():
    hosts = [
        ("125.132.13.175", 58020),
        ("192.168.0.220", 8022),
    ]
    password = "12345678"
    usernames = ["u0_a172", "u0_a173", "u0_a174", "u0_a171", "u0_a170", "root"]

    for host, port in hosts:
        print(f"[*] Probing TCP {host}:{port}...")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            res = s.connect_ex((host, port))
            s.close()
            if res != 0:
                print(f"[-] TCP {host}:{port} unreachable (code {res})")
                continue
            print(f"[+] TCP {host}:{port} is OPEN!")
        except Exception as e:
            print(f"[-] TCP error: {e}")
            continue

        # Try connecting with paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Try without specific username or try common termux usernames
        for user in usernames:
            try:
                print(f"[*] Trying SSH auth {user}@{host}:{port}...")
                client.connect(host, port=port, username=user, password=password, timeout=8)
                print(f"[+] SUCCESS! Authenticated as {user} on {host}:{port}")

                stdin, stdout, stderr = client.exec_command("uname -a && getprop ro.product.cpu.abi && whoami && termux-info")
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                print("=== DEVICE INFO ===")
                print(out)
                if err:
                    print("[STDERR]", err)
                client.close()
                return (host, port, user)
            except paramiko.AuthenticationException:
                print(f"[-] Auth failed for {user}")
            except Exception as e:
                print(f"[-] Error connecting with {user}: {e}")

    print("[-] All connection attempts exhausted.")
    return None

if __name__ == "__main__":
    probe_and_connect()
