// Markdown as st.markdown shows an assessment or a case commentary: headings, paragraphs, lists, pipe tables, code,
// quotes and rules; inline code, bold, italic, links and backslash escapes. Built as DOM nodes, so text never
// becomes HTML. shortcut: no nested lists, setext headings or reference links; upgrade if commentary needs them.
import { h } from "../lib/dom.js";

const INLINE = /(`+)([\s\S]*?)\1|\*\*([\s\S]+?)\*\*|\*([^*\s](?:[\s\S]*?[^*\s])?)\*|\[([^\]]+)\]\(([^)\s]+)\)|\\([\\`*_{}[\]()#+\-.!|$>~])/g;

export function inline(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(h("code", null, m[2]));
    else if (m[3] !== undefined) out.push(h("strong", null, inline(m[3])));
    else if (m[4] !== undefined) out.push(h("em", null, inline(m[4])));
    else if (m[5] !== undefined) out.push(/^(https?:|mailto:|\/)/.test(m[6]) ? h("a", { href: m[6], target: "_blank", rel: "noopener" }, inline(m[5])) : m[0]);
    else out.push(m[7]);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const LIST = /^ {0,3}([-*+]|\d{1,9}[.)])(?:[ \t]+(.*)|[ \t]*)$/;
const RULE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const DIVIDER = /^ *\|? *:?-+:? *(\| *:?-+:? *)*\|? *$/;
const cells = (line) => line.trim().replace(/^\|/, "").replace(/(?<!\\)\|$/, "").split(/(?<!\\)\|/).map((c) => c.trim());

export function markdown(src) {
  const lines = String(src).replace(/\r\n?/g, "\n").split("\n");
  const out = [], para = [];
  const flush = () => {
    if (para.length) out.push(h("p", null, inline(para.join("\n"))));
    para.length = 0;
  };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    let m;
    if (!line.trim()) { flush(); i++; continue; }
    if ((m = /^ {0,3}(`{3,}|~{3,})/.exec(line))) {
      flush();
      const body = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith(m[1]); i++) body.push(lines[i]);
      out.push(h("pre", { class: "sg-code g10-code" }, body.join("\n")));
      i++;
      continue;
    }
    if ((m = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/.exec(line))) {
      flush();
      out.push(h(`h${m[1].length}`, null, inline(m[2] ?? "")));
      i++;
      continue;
    }
    if (RULE.test(line)) { flush(); out.push(h("hr")); i++; continue; }
    if (/^ {0,3}>/.test(line)) {
      flush();
      const body = [];
      while (i < lines.length && /^ {0,3}>/.test(lines[i])) body.push(lines[i++].replace(/^ {0,3}> ?/, ""));
      out.push(h("blockquote", null, markdown(body.join("\n"))));
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && DIVIDER.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      flush();
      const head = cells(line);
      const rows = [];
      for (i += 2; i < lines.length && lines[i].trim() && lines[i].includes("|"); i++) rows.push(cells(lines[i]));
      out.push(h("div", { class: "g10-md-table" }, h("table", null,
        h("thead", null, h("tr", null, head.map((c) => h("th", null, inline(c))))),
        h("tbody", null, rows.map((r) => h("tr", null, head.map((_, j) => h("td", null, inline(r[j] ?? "")))))))));
      continue;
    }
    if ((m = LIST.exec(line))) {
      flush();
      const ordered = /\d/.test(m[1]);
      const items = [];
      while (i < lines.length) {
        const item = LIST.exec(lines[i]);
        if (item && /\d/.test(item[1]) === ordered) items.push([item[2] ?? ""]);
        else if (lines[i].trim() && /^\s/.test(lines[i]) && items.length) items[items.length - 1].push(lines[i].trim());
        else break;
        i++;
      }
      const start = ordered ? parseInt(m[1], 10) : 1;
      out.push(h(ordered ? "ol" : "ul", { start: ordered && start !== 1 ? start : null },
        items.map((t) => h("li", null, inline(t.join("\n"))))));
      continue;
    }
    para.push(line);
    i++;
  }
  flush();
  return out;
}
