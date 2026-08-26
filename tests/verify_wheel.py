import zipfile
import re

wheel_path = "dist/termux_llamacpp-1.0.0b1-py3-none-any.whl"
with zipfile.ZipFile(wheel_path) as z:
    for filename in z.namelist():
        content = z.read(filename)
        # Verify no HTML entities in source files
        if filename.endswith(".py") or filename.endswith(".sh"):
            assert b"&gt;" not in content, f"HTML entity &gt; found in {filename}"
            assert b"&lt;" not in content, f"HTML entity &lt; found in {filename}"
            assert b"&amp;" not in content, f"HTML entity &amp; found in {filename}"

print("All wheel source files validated: 100% clean and free of HTML entities!")
