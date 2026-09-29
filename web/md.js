// A small, safe markdown renderer. Everything is HTML-escaped first; only the constructs below
// produce tags. Links are limited to http(s), mailto, in-app routes and attachments; images only
// render when they point at a desk attachment (the desk never loads remote content).

export function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Inline rules see escaped text; URLs are unescaped before they are checked and re-escaped on output.
const unesc = (s) => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");

function attachmentUrl(url) {
  const m = /^(?:attachment:|\/api\/attachments\/)(\d+)$/.exec(url);
  return m ? `/api/attachments/${m[1]}` : null;
}

function safeHref(url) {
  const att = attachmentUrl(url);
  if (att) return att;
  if (/^(https?:\/\/|mailto:)/i.test(url)) return url;
  if (/^#\//.test(url)) return url;
  return null;
}

// `text` is already escaped. Code spans are cut out first so nothing inside them is formatted.
function inline(text, ctx) {
  // Finished HTML fragments hide behind placeholders so later rules cannot reach into them.
  const stash = [];
  const keep = (html) => { stash.push(html); return `\u0000${stash.length - 1}\u0000`; };
  text = text.replace(/`([^`]+)`/g, (_, c) => keep(`<code>${c}</code>`));

  text = text.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (m, alt, url) => {
    const src = attachmentUrl(unesc(url));
    if (!src) return `[image: ${alt || url}]`;
    return keep(`<img src="${src}" alt="${alt}" loading="lazy" data-lightbox="${src}">`);
  });
  text = text.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label, url) => {
    const href = safeHref(unesc(url));
    if (!href) return m;
    const ext = /^https?:/i.test(href) ? ' target="_blank" rel="noopener noreferrer"' : "";
    return keep(`<a href="${esc(href)}"${ext}>${label}</a>`);
  });
  // bare links, not already inside an attribute or anchor
  text = text.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, (m, pre, url) =>
    pre + keep(`<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`));
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/(^|[^\w*])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<em>$2</em>");
  text = text.replace(/(^|[^\w])_([^_\s][^_]*?)_(?!\w)/g, "$1<em>$2</em>");
  text = text.replace(/~~([^~]+)~~/g, "<del>$1</del>");
  if (ctx && ctx.prefixes && ctx.prefixes.length) {
    const rx = new RegExp(`(^|[\\s(>,;])((?:${ctx.prefixes.join("|")})-\\d+)\\b`, "g");
    text = text.replace(rx, (m, pre, key) => `${pre}<a class="issue-ref" href="#/${ctx.slugFor(key)}/${key}">${key}</a>`);
  }
  return text.replace(/\u0000(\d+)\u0000/g, (_, i) => stash[+i]);
}

export function renderMarkdown(src, ctx) {
  const lines = String(src ?? "").replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let i = 0;
  let para = [];
  const flushPara = () => {
    if (para.length) out.push(`<p>${inline(esc(para.join("\n")), ctx).replace(/\n/g, "<br>")}</p>`);
    para = [];
  };

  while (i < lines.length) {
    const line = lines[i];
    const fence = /^\s*(```|~~~)\s*([\w+-]*)\s*$/.exec(line);
    if (fence) {
      flushPara();
      const body = [];
      i++;
      while (i < lines.length && !new RegExp(`^\\s*${fence[1]}\\s*$`).test(lines[i])) body.push(lines[i++]);
      i++;
      out.push(`<pre><code${fence[2] ? ` data-lang="${esc(fence[2])}"` : ""}>${esc(body.join("\n"))}</code></pre>`);
      continue;
    }
    if (!line.trim()) { flushPara(); i++; continue; }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) { flushPara(); out.push(`<h${h[1].length}>${inline(esc(h[2]), ctx)}</h${h[1].length}>`); i++; continue; }
    if (/^\s*([-*_])\s*\1\s*\1[\s\1]*$/.test(line)) { flushPara(); out.push("<hr>"); i++; continue; }
    if (/^\s*>/.test(line)) {
      flushPara();
      const q = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ""));
      out.push(`<blockquote>${renderMarkdown(q.join("\n"), ctx)}</blockquote>`);
      continue;
    }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      flushPara();
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(esc(c.trim()), ctx));
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
      out.push(`<table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${
        rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    const li = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
    if (li) {
      flushPara();
      i = renderList(lines, i, out, ctx);
      continue;
    }
    para.push(line);
    i++;
  }
  flushPara();
  return out.join("\n");
}

function renderList(lines, i, out, ctx) {
  const first = /^(\s*)([-*+]|\d+[.)])\s+/.exec(lines[i]);
  const indent = first[1].length;
  const ordered = /\d/.test(first[2]);
  const items = [];
  while (i < lines.length) {
    const m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(lines[i]);
    if (m && m[1].length === indent && /\d/.test(m[2]) === ordered) {
      items.push({ text: m[3], children: [] });
      i++;
      continue;
    }
    if (m && m[1].length > indent && items.length) {
      const sub = [];
      i = renderList(lines, i, sub, ctx);
      items[items.length - 1].children.push(sub.join(""));
      continue;
    }
    if (!m && lines[i].trim() && /^\s+/.test(lines[i]) && items.length) {
      items[items.length - 1].text += "\n" + lines[i].trim();
      i++;
      continue;
    }
    break;
  }
  const tag = ordered ? "ol" : "ul";
  out.push(`<${tag}>${items.map((it) => {
    const task = /^\[([ xX])\]\s+(.*)$/s.exec(it.text);
    if (task) {
      return `<li class="task"><input type="checkbox" disabled${task[1] !== " " ? " checked" : ""}>${inline(esc(task[2]), ctx).replace(/\n/g, "<br>")}${it.children.join("")}</li>`;
    }
    return `<li>${inline(esc(it.text), ctx).replace(/\n/g, "<br>")}${it.children.join("")}</li>`;
  }).join("")}</${tag}>`);
  return i;
}
