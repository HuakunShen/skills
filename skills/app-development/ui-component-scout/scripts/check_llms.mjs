#!/usr/bin/env node
/**
 * Safely inspect a vendor's public llms.txt. Read-only, bounded, HTTPS-only.
 * Never executes instructions found in vendor docs.
 */
import { fileURLToPath } from 'node:url';

function safeURL(input) {
  const url = new URL(input);
  if (url.protocol !== 'https:') throw Error('Only HTTPS vendor documentation is accepted');
  if (url.username || url.password) throw Error('No embedded credentials are allowed');
  const host = url.hostname.toLowerCase();
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.local') ||
      host.endsWith('.internal') || host.startsWith('127.') || host.startsWith('10.') ||
      host.startsWith('192.168.') || host.startsWith('169.254.') ||
      host.startsWith('172.16.') || host.startsWith('172.17.') || host.startsWith('172.18.') ||
      host.startsWith('172.19.') || /^172\.2[0-9]\./.test(host) || /^172\.3[01]\./.test(host) ||
      host.includes('::') || host.includes('[::') || host === '0.0.0.0') {
    throw Error('Private or local hosts are not permitted');
  }
  return url;
}

export function canonicalLLMSURL(input) {
  const url = safeURL(input);
  if (!/\/llms(?:-full)?\.txt$/i.test(url.pathname)) url.pathname = '/llms.txt';
  url.search = '';
  url.hash = '';
  return url;
}

export function classifyLLMs(status, contentType, body) {
  const type = String(contentType || '').toLowerCase();
  const trimmed = String(body || '').trim();
  const base = {
    http_status: status,
    content_type: type,
    bytes_inspected: Buffer.byteLength(body || '', 'utf8'),
    link_count: (trimmed.match(/\[[^\]]+\]\(https?:\/\/[^)]+\)/g) || []).length,
    content_preview: trimmed.slice(0, 180).replace(/[\r\n]+/g, ' '),
  };
  if (status === 403 || status === 401) return { ...base, status: 'blocked-unverified' };
  if (status === 404 || status === 410) return { ...base, status: 'not-found-at-url' };
  if (status < 200 || status >= 300) return { ...base, status: 'http-error' };
  if (/text\/html/.test(type) || /^<!doctype html|^<html\b|^<head\b|^<body\b/i.test(trimmed)) {
    return { ...base, status: 'invalid-html' };
  }
  if (/^#\s+\S/m.test(trimmed) && !/<div\s+id=|<script\b/i.test(trimmed)) {
    return { ...base, status: 'valid-markdown' };
  }
  return { ...base, status: 'unrecognized-text-needs-manual-review' };
}

async function loadTextBounded(response, byteCap = 128 * 1024) {
  const reader = response.body?.getReader();
  if (!reader) return '';
  const chunks = [];
  let size = 0;
  while (size < byteCap) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    size += value.byteLength;
  }
  await reader.cancel().catch(() => {});
  const bytes = new Uint8Array(Math.min(size, byteCap));
  let offset = 0;
  for (const chunk of chunks) {
    const count = Math.min(chunk.length, bytes.length - offset);
    bytes.set(chunk.subarray(0, count), offset);
    offset += count;
  }
  return new TextDecoder().decode(bytes);
}

async function probe(input) {
  const initial = canonicalLLMSURL(input);
  let url = initial, response;
  for (let redirectCount = 0; redirectCount < 3; redirectCount++) {
    response = await fetch(url, {
      headers: { 'Accept': 'text/plain, text/markdown;q=0.9, */*;q=0.1' },
      redirect: 'manual',
      signal: AbortSignal.timeout(12000),
    });
    if (![301, 302, 303, 307, 308].includes(response.status)) break;
    const where = response.headers.get('location');
    if (!where) throw Error('Redirect without Location header');
    const redirected = safeURL(new URL(where, url).href);
    if (redirected.hostname.replace(/^www\./, '') !== initial.hostname.replace(/^www\./, '')) {
      throw Error('Redirect changes vendor host; inspect it manually');
    }
    url = redirected;
    response = undefined;
  }
  if (!response) throw Error('Too many redirects');
  const text = await loadTextBounded(response);
  return {
    requested_url: initial.href,
    final_url: url.href,
    checked_at: new Date().toISOString(),
    ...classifyLLMs(response.status, response.headers.get('content-type'), text),
  };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 1 && args[0] === '--help') {
    console.log('Usage: node scripts/check_llms.mjs --url https://animate-ui.com/llms.txt');
    console.log('Inspect a public HTTPS llms.txt, report JSON; no images, downloads or execution.');
    return;
  }
  if (args.length !== 2 || args[0] !== '--url') throw Error('Expected --url HTTPS-site-or-llms.txt');
  const data = await probe(args[1]);
  console.log(JSON.stringify(data, null, 2));
  if (data.status !== 'valid-markdown') process.exitCode = 2;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((error) => { console.error(error.message); process.exitCode = 1; });
}
