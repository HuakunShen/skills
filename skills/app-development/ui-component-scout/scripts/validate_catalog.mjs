#!/usr/bin/env node
// Validate official-text inventory, curated overlay, and absence of image assets.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const refPath = (name) => path.join(root, 'references', name);
const issues = [], warnings = [], seen = new Set(), libraries = new Map();
let dupes = 0, ambiguous = 0, inventory = [], curation = {};

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const filePath = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(filePath) : [filePath];
  });
}

try {
  inventory = fs.readFileSync(refPath('catalog.jsonl'), 'utf8').split(/\r?\n/).filter(Boolean).map((line, i) => {
    try {
      const item = JSON.parse(line);
      for (const name of ['library', 'framework', 'title', 'url']) {
        if (!item[name] || typeof item[name] !== 'string') issues.push('Catalog row ' + (i + 1) + ' missing ' + name);
      }
      try { if (!['https:', 'http:'].includes(new URL(item.url).protocol)) issues.push('Bad protocol at ' + i); }
      catch { issues.push('Invalid URL at row ' + (i + 1)); }
      const key = item.library + '|' + item.url;
      if (seen.has(key)) dupes++;
      seen.add(key);
      if (item.url.endsWith('/get-started/index')) ambiguous++;
      libraries.set(item.library, (libraries.get(item.library) || 0) + 1);
      return item;
    } catch (error) {
      issues.push('Catalog row ' + (i + 1) + ': ' + error.message);
      return null;
    }
  }).filter(Boolean);
} catch (error) { issues.push('Cannot read catalog: ' + error.message); }

try {
  const body = fs.readFileSync(refPath('curated.json'), 'utf8');
  curation = JSON.parse(body);
  if (/"screenshot"|"screenshot_library_url"/.test(body)) issues.push('Screenshot/image fields in curated overlay');
  if (!Array.isArray(curation.curated) || !Array.isArray(curation.additional_research)) {
    issues.push('Expected curated and additional_research arrays');
  } else {
    [...curation.curated, ...curation.additional_research].forEach((x, i) => {
      if (!x.library || !x.name || !x.url || !Array.isArray(x.scenarios)) issues.push('Curated row ' + (i + 1) + ' missing identity/scenarios');
      if (!x.evidence || !x.design_role || !x.motion_policy) issues.push('Curated row ' + (i + 1) + ' missing quality metadata');
    });
  }
} catch (error) { issues.push('Cannot read curated overlay: ' + error.message); }

let images = 0;
for (const filepath of walk(root)) {
  if (/\.(png|jpe?g|gif|webp|avif|svg|ico|bmp|tiff?|heic|mp4|mov|webm)$/i.test(filepath)) {
    images++;
    issues.push('Forbidden media asset: ' + path.relative(root, filepath));
  }
}
if (dupes) warnings.push(dupes + ' repeated library+URL pairs in historical raw index');
if (ambiguous) warnings.push(ambiguous + ' generic/get-started URLs; verify exact docs live');

const report = {
  snapshot_date: '2026-11-04',
  inventory_count: inventory.length,
  source_count: libraries.size,
  curated_count: (curation.curated?.length || 0) + (curation.additional_research?.length || 0),
  images,
  duplicate_source_urls: dupes,
  ambiguous_urls: ambiguous,
  issues,
  warnings,
};
console.log(JSON.stringify(report, null, 2));
if (issues.length) process.exitCode = 1;
