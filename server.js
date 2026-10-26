const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, 'public');
const development = process.argv.includes('--dev');
function revision() {
  return ['index.html', 'style.css', 'app.js', 'sync-data.js', 'tencent-data.json', 'profiles.js', 'profile-config.json', 'organizations.js', 'organization-data.json', 'people-data.json', 'customer-system.js', 'customer-system.json', 'award-history.js', 'award-history.json', 'partners.js', 'cooperation-partners.json', 'worklogs.js', 'worklogs.json', 'worklog-config.json', 'sheet-columns.json'].map(name => {
    try { return fs.statSync(path.join(root, name)).mtimeMs; }
    catch { return 'missing'; }
  }).join('-');
}
http.createServer((req,res)=>{
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (development) res.setHeader('Cache-Control', 'no-store');
  if (development && pathname === '/__dev_revision') {
    res.setHeader('Content-Type', 'text/plain');
    return res.end(revision());
  }
  const file = path.join(root, pathname === '/' ? 'index.html' : pathname);
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
  fs.readFile(file,(err,data)=>{
    if(err){res.writeHead(404);return res.end('Not found');}
    res.setHeader('Content-Type', ({'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8'})[path.extname(file)] || 'application/octet-stream');
    if (development && path.extname(file) === '.html') {
      const reload = `<script>(()=>{let version=${JSON.stringify(revision())};setInterval(async()=>{try{const response=await fetch('/__dev_revision',{cache:'no-store'});if(response.ok&&await response.text()!==version)location.reload();}catch{}},1000);})();</script>`;
      return res.end(data.toString().replace('</body>', reload + '</body>'));
    }
    res.end(data);
  });
}).listen(process.env.PORT || 3000, '0.0.0.0');
