import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';

const skillRoot = path.resolve(import.meta.dirname, '..');

function run(script, args = []) {
  return spawnSync(process.execPath, [path.join(skillRoot, 'scripts', script), ...args], {
    cwd: skillRoot,
    encoding: 'utf8',
  });
}

test('offline component inventory is valid and the entire skill stays text-only', () => {
  const result = run('validate_catalog.mjs');
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.inventory_count, 2661);
  assert.equal(report.curated_count, 51);
  assert.equal(report.images, 0);
});

test('AI Chat lookup finds genuine scenario matches with provenance', () => {
  const result = run('search_catalog.mjs', ['--query', 'AI chat context', '--framework', 'react', '--limit', '8', '--json']);
  assert.equal(result.status, 0, result.stderr);
  const matches = JSON.parse(result.stdout);
  assert.ok(matches.length > 0);
  assert.ok(matches.some(x => /Kokonut UI|Eased UI|SmoothUI/.test(x.library)));
  assert.ok(matches.every(x => x.url && x.provenance));
});

test('framework filter excludes other frameworks even when wording matches', () => {
  const result = run('search_catalog.mjs', ['--query', 'podcast', '--framework', 'svelte', '--limit', '15', '--json']);
  assert.equal(result.status, 0, result.stderr);
  const matches = JSON.parse(result.stdout);
  assert.ok(matches.every(x => x.frameworks.some(f => f.toLowerCase() === 'svelte')));
});

test('paid components retain their tier and must not be silently offered as free', () => {
  const result = run('search_catalog.mjs', ['--query', 'agent run console', '--limit', '10', '--json']);
  assert.equal(result.status, 0, result.stderr);
  const matches = JSON.parse(result.stdout);
  const consoleEntry = matches.find(x => /Agent Run Console/i.test(x.title));
  assert.ok(consoleEntry, 'Expected a curated Eased Agent Run Console record');
  assert.equal(consoleEntry.tier, 'pro');
});

test('bundle contains no image files and curated entries have no screenshot fields', () => {
  const disallowed = /\.(png|jpe?g|gif|webp|avif|svg|mp4|webm)$/i;
  function check(dir) {
    for (const item of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, item.name);
      if (item.isDirectory()) check(full);
      else assert.doesNotMatch(item.name, disallowed, `Image or video file: ${full}`);
    }
  }
  check(skillRoot);
  const curated = readFileSync(path.join(skillRoot, 'references', 'curated.json'), 'utf8');
  assert.doesNotMatch(curated, /"screenshot"|"screenshot_library_url"/);
});
