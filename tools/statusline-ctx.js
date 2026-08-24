// عدّاد سياق حيّ لـClaude Code — يقرأ ذيل الترانسكربت ويحسب ما يُعاد شحنه كل دور
const fs = require('fs');
const R='\x1b[0m', DIM='\x1b[2m', G='\x1b[32m', Y='\x1b[33m', RD='\x1b[1;31m', C='\x1b[36m';


function lastUsage(p) {
  try {
    const size = fs.statSync(p).size;
    const len = Math.min(size, 512 * 1024);
    const buf = Buffer.alloc(len);
    const fd = fs.openSync(p, 'r');
    fs.readSync(fd, buf, 0, len, size - len);
    fs.closeSync(fd);
    const lines = buf.toString('utf8').split('\n');
    for (let i = lines.length - 1; i >= 0; i--) {
      if (!lines[i].includes('usage')) continue;
      try {
        const u = JSON.parse(lines[i]).message?.usage;
        if (u) return u;
      } catch (e) {}
    }
  } catch (e) {}
  return null;
}

function main(d) {
  const u = lastUsage(d.transcript_path);
  const model = d.model?.display_name || '?';
  let out = `${C}${model}${R}`;

if (u) {
  const cc = typeof u.cache_creation_input_tokens === 'number' ? u.cache_creation_input_tokens : 0;
  const ctx = (u.input_tokens || 0) + cc + (u.cache_read_input_tokens || 0);
  const k = Math.round(ctx / 1000);
  const pct = Math.min(100, Math.round((ctx / 200000) * 100));
  const filled = Math.round(pct / 12.5);
  const bar = '\u2593'.repeat(filled) + '\u2591'.repeat(8 - filled);
  const col = ctx > 200000 ? RD : ctx > 100000 ? Y : G;
  out += ` ${DIM}\u00b7${R} ${col}ctx ${k}k ${bar} ${pct}%${R}`;
  if (ctx > 200000) out += ` ${RD}\u26a0 START A NEW CHAT${R}`;
  else if (ctx > 100000) out += ` ${Y}\u26a0 wrap up soon${R}`;
}

const usd = d.cost?.total_cost_usd;
if (typeof usd === 'number') out += ` ${DIM}\u00b7 $${usd.toFixed(2)}${R}`;
process.stdout.write(out);
}

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => raw += c);
process.stdin.on('end', () => {
  let d = {};
  try { d = JSON.parse(raw); } catch (e) {}
  try { main(d); } catch (e) { process.stdout.write('ctx ?'); }
});
