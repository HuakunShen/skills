#!/usr/bin/env node
// Read-only offline search; installation and live verification are separate.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const refPath = (name) => path.join(root, 'references', name);
const readJSON = (name) => JSON.parse(fs.readFileSync(refPath(name), 'utf8'));

function parseArgs(args) {
  const opts = { query: '', scenario: '', framework: '', role: '', curatedOnly: false, limit: 12, json: false };
  const help = [
    'Usage: node scripts/search_catalog.mjs [options]',
    '--query "text" --scenario id --framework react|vue|svelte|solid',
    '--role foundation|animated-primitive|signature-design|showpiece',
    '--curated-only --limit 1..100 --json --help',
  ].join('\n');
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === '--help' || arg === '-h') { console.log(help); process.exit(0); }
    if (arg === '--json') { opts.json = true; continue; }
    if (arg === '--curated-only') { opts.curatedOnly = true; continue; }
    if (!['--query', '--scenario', '--framework', '--role', '--limit'].includes(arg)) throw Error('Unknown flag: ' + arg + '\n' + help);
    const value = args[++i];
    if (!value || value.startsWith('--')) throw Error('Missing value for ' + arg);
    const name = arg.slice(2);
    opts[name] = name === 'limit' ? Number(value) : value.trim();
  }
  opts.framework = opts.framework.toLowerCase();
  opts.role = opts.role.toLowerCase();
  if (opts.framework && !['react', 'vue', 'svelte', 'solid'].includes(opts.framework)) throw Error('Invalid --framework');
  if (opts.role && !['foundation', 'animated-primitive', 'signature-design', 'showpiece'].includes(opts.role)) throw Error('Invalid --role');
  if (!Number.isInteger(opts.limit) || opts.limit < 1 || opts.limit > 100) throw Error('--limit must be 1..100');
  return opts;
}

function frameworkList(value) {
  if (Array.isArray(value)) return value.map(String).map(x => x.trim()).filter(Boolean);
  return String(value || '').split(/\s*[+,/]\s*/).filter(Boolean);
}

function loadRecords(curatedOnly) {
  const data = readJSON('curated.json');
  const profiles = new Map(data.source_profiles.map(x => [x.library, x]));
  const curated = [...data.curated, ...data.additional_research].map((x, index) => {
    const frameworks = frameworkList(profiles.get(x.library)?.frameworks || ['React']);
    return {
      library: x.library, title: x.name, url: x.url, description: x.note_zh || '',
      frameworks, framework_compatibility: frameworks.length > 1 ? 'site-level support; verify exact component' : 'site-native claimed; verify exact component',
      scenarios: x.scenarios || [], category: '', design_role: x.design_role || 'unknown',
      motion_policy: x.motion_policy || 'unknown', tier: x.tier || 'unverified',
      evidence: x.evidence || 'unknown', provenance: 'curation:' + (x.evidence || 'unknown'),
      curated: true, _order: index,
    };
  });
  if (curatedOnly) return curated;
  const urlSet = new Set(curated.map(x => x.library.toLowerCase() + '|' + x.url));
  const other = fs.readFileSync(refPath('catalog.jsonl'), 'utf8').trim().split(/\r?\n/).map(JSON.parse)
    .map((x, index) => ({
      library: x.library, title: x.title, url: x.url, description: x.description || '',
      frameworks: frameworkList(x.framework), framework_compatibility: 'snapshot-listed; verify exact component',
      scenarios: [], category: x.category || '', design_role: 'unknown', motion_policy: 'unknown',
      tier: x.tier || 'unverified', evidence: x.confidence || 'official-description',
      provenance: 'official-snapshot:' + (x.data_source || 'unknown'), curated: false, _order: curated.length + index,
    }))
    .filter(x => !urlSet.has(x.library.toLowerCase() + '|' + x.url));
  return [...curated, ...other];
}

function termsFor(query) {
  const str = query.toLowerCase().trim();
  const terms = str.match(/[\p{L}\p{N}_.-]+/gu) || [];
  const aliases = {
    '聊天': ['chat', 'ai', 'composer'], '智能体': ['agent', 'task'], '代理': ['agent', 'session'],
    '动画': ['animation', 'motion'], '动效': ['animation', 'motion'],
    '代码': ['code', 'viewer'], '音频': ['audio', 'podcast'], '播客': ['podcast', 'player'],
    '视频': ['video', 'media'], '表格': ['table', 'datatable'], '图表': ['chart', 'analytics'],
    '快捷键': ['keyboard', 'hotkey'], '鼠标': ['cursor', 'click'], '工作流': ['workflow', 'agent'],
    '流程图': ['graph', 'node'], '网络': ['network', 'graph'], '卡片': ['card', 'folded'],
  };
  for (const [needle, expansion] of Object.entries(aliases)) if (str.includes(needle)) terms.push(...expansion);
  return [...new Set(terms.filter(x => x.length > 1))];
}

function score(x, opts, tokens) {
  if (opts.framework && !x.frameworks.some(f => f.toLowerCase() === opts.framework)) return -1;
  if (opts.role && opts.role !== x.design_role) return -1;
  if (opts.scenario && !x.scenarios.includes(opts.scenario)) return -1;
  let result = x.curated ? 8 : 0;
  if (!tokens.length) return result + (opts.scenario ? 40 : 0) + (opts.role ? 5 : 0);
  const fields = [
    [x.title.toLowerCase(), 12], [x.scenarios.join(' ').toLowerCase(), 9],
    [x.category.toLowerCase(), 7], [x.library.toLowerCase(), 5],
    [x.description.toLowerCase(), 3],
  ];
  let matched = 0;
  for (const term of tokens) {
    let weight = 0;
    for (const [field, points] of fields) if (field.includes(term)) weight = Math.max(weight, points);
    if (weight) { matched++; result += weight; }
  }
  if (!matched) return -1;
  if (opts.query && (x.title.toLowerCase().includes(opts.query.toLowerCase()) ||
    x.scenarios.join(' ').toLowerCase().includes(opts.query.toLowerCase()))) result += 25;
  result += matched / tokens.length * 12;
  if (opts.scenario) result += 40;
  if (x.url.endsWith('/get-started/index')) result -= 20; // ambiguous source fallback link
  return result;
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const tokens = termsFor(opts.query);
  const all = loadRecords(opts.curatedOnly).map(x => ({ ...x, _score: score(x, opts, tokens) }))
    .filter(x => x._score >= 0).sort((a, b) => b._score - a._score || a._order - b._order);
  const seen = new Set();
  const results = all.filter(x => {
    const key = x.library + '|' + x.title + '|' + x.url;
    if (seen.has(key)) return false;
    seen.add(key); return true;
  }).slice(0, opts.limit).map(({ _score, _order, ...x }) => ({ ...x, relevance: Number(_score.toFixed(2)) }));
  if (opts.json) return console.log(JSON.stringify(results, null, 2));
  if (!results.length) return console.log('No offline results; broaden query or verify vendor docs live.');
  results.forEach((x, i) => {
    console.log((i + 1) + '. ' + x.library + ' — ' + x.title + ' [' + x.frameworks.join(', ') + ']');
    console.log('   ' + x.url);
    console.log('   role=' + x.design_role + ' motion=' + x.motion_policy + ' tier=' + x.tier + ' evidence=' + x.evidence);
    console.log('   ' + x.description.slice(0, 330));
    console.log('   provenance=' + x.provenance + ' / ' + x.framework_compatibility);
  });
  console.log('\nHistorical offline index. Verify vendor docs, actual motion, license and version.');
}

try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
