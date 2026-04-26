import json
import base64
from pathlib import Path

with open("training/dataset.json") as f:
    data = json.load(f)

rows = ""
for i, record in enumerate(data):
    img_path = Path(record["image"])
    img_b64 = base64.b64encode(img_path.read_bytes()).decode()
    ext = img_path.suffix.lstrip(".")
    aria = record["aria_label"].replace("<", "&lt;").replace(">", "&gt;")
    rows += f"""
<div class="record">
  <div class="record-num">#{i} — {img_path.name}</div>
  <img src="data:image/{ext};base64,{img_b64}" />
  <div class="label">{aria}</div>
</div>"""

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>CivicInsight Dataset Review</title>
<style>
  body {{ font-family: sans-serif; font-size: 14px; background: #f5f5f5; margin: 0; padding: 20px; }}
  .record {{ background: #fff; border: 1px solid #ddd; border-radius: 6px; margin-bottom: 24px; padding: 16px; }}
  .record-num {{ font-size: 11px; color: #999; margin-bottom: 8px; }}
  .record img {{ max-width: 100%; height: auto; display: block; margin-bottom: 12px; }}
  .label {{ line-height: 1.7; color: #222; white-space: pre-wrap; background: #f9f9f9; padding: 12px; border-radius: 4px; border-left: 3px solid #4a90e2; }}
</style>
</head>
<body>
<h2>CivicInsight — Dataset Review ({len(data)} records)</h2>
{rows}
</body>
</html>"""

out = Path("training/review.html")
out.write_text(html)
print(f"Written: {out} ({out.stat().st_size // 1024} KB)")
