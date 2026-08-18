// Verify that the fa and en translation dictionaries in the client-side JS
// files expose the same keys with non-empty values, so a missing string can
// never silently fall back to the other language.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const files = ["static/landing/js/chat.js", "static/landing/js/demo.js"];

let failed = false;

function balancedBlock(source, openIndex) {
  let depth = 0;
  for (let i = openIndex; i < source.length; i++) {
    const ch = source[i];
    if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(openIndex + 1, i);
    }
  }
  throw new Error("unbalanced braces");
}

function keysOf(objText) {
  const keys = new Set();
  const re = /^\s*([A-Za-z_$][\w$]*)\s*:/gm;
  let match;
  while ((match = re.exec(objText))) keys.add(match[1]);
  return keys;
}

function emptyValues(objText) {
  const empty = [];
  const re = /^\s*([A-Za-z_$][\w$]*)\s*:\s*""\s*,?\s*$/gm;
  let match;
  while ((match = re.exec(objText))) empty.push(match[1]);
  return empty;
}

function languageBlock(source, language) {
  const index = source.indexOf(`var T`);
  if (index === -1) throw new Error("no `var T` dictionary found");
  const outerOpen = source.indexOf("{", index);
  const outer = balancedBlock(source, outerOpen);
  const re = new RegExp(`\\b${language}\\s*:`);
  const langIndex = outer.search(re);
  if (langIndex === -1) throw new Error(`no "${language}" language block`);
  const blockOpen = outer.indexOf("{", langIndex);
  return balancedBlock(outer, blockOpen);
}

for (const file of files) {
  const path = join(root, file);
  const source = readFileSync(path, "utf8");
  const fa = languageBlock(source, "fa");
  const en = languageBlock(source, "en");
  const faKeys = keysOf(fa);
  const enKeys = keysOf(en);

  const faOnly = [...faKeys].filter((key) => !enKeys.has(key));
  const enOnly = [...enKeys].filter((key) => !faKeys.has(key));
  const faEmpty = emptyValues(fa);
  const enEmpty = emptyValues(en);

  if (faOnly.length || enOnly.length || faEmpty.length || enEmpty.length) {
    failed = true;
    console.error(`✗ ${file}`);
    if (faOnly.length) console.error(`  missing in en: ${faOnly.join(", ")}`);
    if (enOnly.length) console.error(`  missing in fa: ${enOnly.join(", ")}`);
    if (faEmpty.length) console.error(`  empty in fa:  ${faEmpty.join(", ")}`);
    if (enEmpty.length) console.error(`  empty in en:  ${enEmpty.join(", ")}`);
  } else {
    console.log(`✓ ${file}: ${faKeys.size} keys match in fa and en`);
  }
}

if (failed) process.exit(1);
