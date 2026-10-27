"""Build a Pages artifact whose HTML always references matching asset versions."""
import hashlib
from pathlib import Path
import re
import shutil

root = Path('/tmp/customer-pages-site')
root.mkdir(parents=True, exist_ok=True)
shutil.copy2('index.html', root/'index.html')
shutil.copy2('.nojekyll', root/'.nojekyll')
shutil.copytree('public', root/'public', dirs_exist_ok=True)
page = root/'public/index.html'
html = page.read_text()
for name in ('style.css', 'app.js', 'sync-data.js', 'profiles.js', 'organizations.js', 'customer-system.js', 'award-history.js', 'partners.js', 'worklogs.js', 'remote-sync.js', 'customer-trees.js'):
    digest = hashlib.sha256((root/'public'/name).read_bytes()).hexdigest()[:12]
    html = re.sub(r'\./' + re.escape(name) + r'(?:\?[^"\s]*)?"', './' + name + '?v=' + digest + '"', html)
page.write_text(html)
print('Prepared Pages site with content-versioned assets')
