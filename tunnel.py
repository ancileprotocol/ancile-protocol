import subprocess

print("=" * 55)
print("Starting Cloudflare tunnel on port 5000...")
print("Look for the URL that says 'trycloudflare.com'")
print("Press Ctrl+C to stop.")
print("=" * 55)

subprocess.run([r"C:\ancile\cloudflared.exe", "tunnel", "--url", "http://localhost:5000"])
