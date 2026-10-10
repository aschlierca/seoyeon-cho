#!/usr/bin/env node
// Runs the Blender asset pipeline.
//   node scripts/blender.mjs build [--force]             writes blender/book.blend from build_book.py
//   node scripts/blender.mjs export [--no-posters|--preview]  writes the GLB, meta JSON, and posters
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const blend = join(root, 'blender', 'book.blend');
const [command, ...flags] = process.argv.slice(2);

function findBlender() {
  const candidates = [
    process.env.BLENDER_BIN,
    '/Applications/Blender.app/Contents/MacOS/Blender',
    'C:\\Program Files\\Blender Foundation\\Blender\\blender.exe',
    'blender',
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (candidate === 'blender' || existsSync(candidate)) return candidate;
  }
  return 'blender';
}

function run(args) {
  const result = spawnSync(findBlender(), args, { cwd: root, stdio: 'inherit' });
  if (result.error) {
    console.error('Could not start Blender. Set BLENDER_BIN to the Blender executable.');
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

if (command === 'build') {
  if (existsSync(blend)) {
    if (!flags.includes('--force')) {
      console.error(
        'blender/book.blend already exists and may hold hand edits, so it was left alone.\n' +
          'To export it for the site:      npm run asset:export\n' +
          'To regenerate it from code:     npm run asset:build -- --force   (the current file is backed up first)',
      );
      process.exit(1);
    }
    const backups = join(root, 'blender', 'backups');
    mkdirSync(backups, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backup = join(backups, `book-${stamp}.blend`);
    copyFileSync(blend, backup);
    console.log(`Backed up the current book.blend to ${backup}`);
  }
  run(['--background', '--factory-startup', '--python', join('blender', 'build_book.py'), '--', ...flags]);
} else if (command === 'export') {
  if (!existsSync(blend)) {
    console.error('blender/book.blend does not exist yet. Run: npm run asset:build');
    process.exit(1);
  }
  run(['--background', '--factory-startup', blend, '--python', join('blender', 'export_book.py'), '--', ...flags]);
} else {
  console.error('Usage: node scripts/blender.mjs <build|export> [flags]');
  process.exit(1);
}
