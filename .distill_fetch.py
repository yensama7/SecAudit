import json, subprocess, sys

idx = sys.argv[1]
out = subprocess.run(
    [sys.executable, "intelligence-engine/report_feed.py", "--source", "sherlock", "--index", idx],
    capture_output=True, text=True, encoding="utf-8"
)
d = json.loads(out.stdout)
if "error" in d:
    print("ERROR", d.get("error"))
    sys.exit(0)
with open(".distill-tmp.txt", "w", encoding="utf-8") as f:
    f.write(d.get("text", ""))
print("INDEX", d["index"], "COUNT", d["count"], "LEN", len(d.get("text", "")), "TRUNC", d.get("truncated"))
print("PATH", d.get("path"))
print("URL", d.get("url"))
