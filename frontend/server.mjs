import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(fileURLToPath(new URL('.', import.meta.url)), 'dist');
const port = Number(process.env.PORT || 4173);

const mimeTypes = {
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
};

function resolvePath(urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0] || '/');
  const safePath = normalize(decoded)
    .replace(/^[/\\]+/, '')
    .replace(/^(\.\.[/\\])+/, '');
  const candidate = join(root, safePath);

  if (existsSync(candidate) && statSync(candidate).isFile()) {
    return candidate;
  }

  return join(root, 'index.html');
}

createServer((req, res) => {
  try {
    const filePath = resolvePath(req.url || '/');
    const ext = extname(filePath);
    res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream');
    createReadStream(filePath).pipe(res);
  } catch {
    res.statusCode = 500;
    res.end('Internal server error');
  }
}).listen(port, '0.0.0.0', () => {
  console.log(`Serving frontend on port ${port}`);
});
