import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyLLMs, canonicalLLMSURL } from '../scripts/check_llms.mjs';

test('200 HTML SPA fallback is not a valid llms.txt', () => {
  const result = classifyLLMs(200, 'text/html; charset=utf-8', '<!doctype html><html><div id="app"></div></html>');
  assert.equal(result.status, 'invalid-html');
});

test('a Markdown site index is recognized and links counted', () => {
  const markdown = '# Animate UI\n\n> Motion Components\n\n## Docs\n- [Combobox](https://animate-ui.com/docs/primitives/base-ui/combobox)\n';
  const result = classifyLLMs(200, 'text/plain', markdown);
  assert.equal(result.status, 'valid-markdown');
  assert.ok(result.link_count > 0);
});

test('403 cannot be inferred to mean does not exist', () => {
  const result = classifyLLMs(403, 'text/html', 'Forbidden');
  assert.equal(result.status, 'blocked-unverified');
});

test('URL builder requires a public HTTPS host and no credentials', () => {
  assert.equal(canonicalLLMSURL('https://animate-ui.com/').href, 'https://animate-ui.com/llms.txt');
  assert.throws(() => canonicalLLMSURL('http://localhost:8080/'));
  assert.throws(() => canonicalLLMSURL('https://user:password@animate-ui.com'));
});
