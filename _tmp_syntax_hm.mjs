import fs from 'node:fs';
import ts from 'typescript';
const src = fs.readFileSync('C:/Users/user/Desktop/dealpulseksa-web/lib/blog.ts', 'utf8');
try {
  const sourceFile = ts.createSourceFile('blog.ts', src, ts.ScriptTarget.Latest, true);
  const errors = sourceFile.parseDiagnostics || [];
  console.log('Parse diagnostics:', errors.length);
  errors.slice(0, 5).forEach(e => console.log(e.messageText));
  console.log('OK - parseable');
} catch (e) {
  console.log('PARSE ERROR:', e.message);
}
