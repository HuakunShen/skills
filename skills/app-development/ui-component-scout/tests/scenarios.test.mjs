import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
function scout(...args) {
  const result = spawnSync(process.execPath, [path.join(root, 'scripts/search_catalog.mjs'), '--json', '--limit', '30', ...args], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

const examples = [
  ['hotkey-onboarding', 'Apple Keyboard'],
  ['computer-use-demo', 'Demo Cursor'],
  ['context-inspector', 'AI Context Meter'],
  ['merge-trace', 'AI Agent Lanes'],
  ['agent-code-demo', 'Code Block'],
  ['device-fabric-illustration', 'Circuit Board'],
  ['activity-heatmap', 'Activity Terrain'],
  ['video-editor', 'Clip Trimmer'],
  ['signature-cards', 'Cutout Card'],
  ['wow-demo', 'Crystalized Ball'],
  ['podcast', 'Synced Transcript'],
];

for (const [scenario, expected] of examples) {
  test('scenario ' + scenario + ' finds ' + expected, () => {
    const result = scout('--scenario', scenario, '--curated-only');
    assert.ok(result.some(x => x.title === expected), 'No expected curated candidate');
  });
}
