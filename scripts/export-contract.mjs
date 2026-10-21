import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const backend = join(root, 'backend');
const python = join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const output = execFileSync(python, ['-m', 'pulse.export_openapi'], { cwd: backend, encoding: 'utf8' });
const schema = JSON.parse(output);
const target = join(root, 'contracts/openapi.json');
const generated = JSON.stringify(schema, null, 2) + '\n';
if (process.argv.includes('--check')) {
  if (readFileSync(target, 'utf8') !== generated) throw new Error('OpenAPI contract is outdated. Run npm run api:generate.');
  console.log('OpenAPI contract is up to date.');
} else {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, generated);
}
