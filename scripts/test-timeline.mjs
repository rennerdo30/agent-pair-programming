// Renderer regression checks without a browser or running desk.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../web/app.js", import.meta.url), "utf8");
const renderer = source.slice(source.indexOf("function timelineHtml(issue)"), source.indexOf("const inBuild ="));
const context = vm.createContext({
  S: { seen: new Set() }, ICON: { build: "" },
  esc: (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;"),
  ago: (s) => s, fullTime: (s) => s, mergedTag: () => "", md: (s) => s,
});
vm.runInContext(renderer, context);
const build = (id, label = `build-${id}`) => ({ id, action: "build", actor: "agent", created_at: String(id).padStart(3, "0"), detail: { label, previous: `build-${id - 1}` } });
const render = (activity, comments = []) => context.timelineHtml({ activity, comments });
for (const size of [1, 2]) {
  const html = render(Array.from({ length: size }, (_, i) => build(i + 1)));
  assert.ok(!html.includes("<details"));
  assert.equal((html.match(/published build /g) || []).length, size);
}
const html = render([build(1), build(2), build(3, '<newest>"')]);
assert.ok(html.includes('published 3 builds · newest'));
assert.ok(html.includes('&lt;newest>&quot;'));
assert.ok(html.includes('title="003">· 003'));
assert.ok(html.includes('<details class="tl-build-run"'));
assert.ok(!html.includes('<details open'));
assert.equal((html.match(/published build /g) || []).length, 3);
assert.ok(html.includes('(was build-2)'));
const comment = { id: 1, created_at: "004", author: "owner", text: "separator", attachments: [] };
const separated = render([1, 2, 3, 5, 6, 7].map((id) => build(id)), [comment]);
assert.equal((separated.match(/<details /g) || []).length, 2);
assert.ok(separated.indexOf('separator') > separated.indexOf('</details>'));
assert.ok(separated.indexOf('separator') < separated.lastIndexOf('<details'));
const edited = { id: 4, created_at: "004", action: "edited", actor: "owner", detail: { fields: ['title'] } };
assert.equal((render([build(1), build(2), build(3), edited, build(5), build(6), build(7)]).match(/<details /g) || []).length, 2);
assert.ok(!render([build(1), build(2), build(4)], [{ ...comment, created_at: "003" }]).includes('<details'));
assert.equal((render([build(3), build(1), build(2)]).match(/published 3 builds/g) || []).length, 1);
assert.ok(render(Array.from({ length: 40 }, (_, i) => build(i + 1))).includes('published 40 builds · newest <span class="build-ref">build-40'));
const sameTime = [build(1), build(2), build(3)].map((a) => ({ ...a, created_at: "001" }));
assert.ok(render(sameTime).includes('newest <span class="build-ref">build-3'));
console.log('Timeline renderer checks passed (threshold, ordering, separators, newest label/time, escaping, retained entries).');
