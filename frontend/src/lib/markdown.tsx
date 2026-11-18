import { Fragment, type ReactNode } from "react";

/**
 * A tiny Markdown renderer for the legal pages (docs/legal/*.md): headings,
 * paragraphs, bullet lists, tables, **bold**, _italic_ and [links](url).
 * It builds React elements, never raw HTML, so nothing in the file can inject markup.
 */
function inline(text: string, key = 0): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|_(.+?)_|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = `${key}-${i++}`;
    if (m[1]) out.push(<strong key={k}>{inline(m[1], i)}</strong>);
    else if (m[2]) out.push(<em key={k}>{inline(m[2], i)}</em>);
    else {
      const href = m[4];
      const safe = /^(https?:|mailto:|\/|#)/.test(href) ? href : "#";
      out.push(
        <a key={k} href={safe}>
          {m[3]}
        </a>,
      );
    }
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (row: string) =>
  row
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const Tag = (level === 1 ? "h1" : level === 2 ? "h2" : "h3") as "h1" | "h2" | "h3";
      const cls =
        level === 1
          ? "mt-2 mb-3 font-heading text-3xl font-bold"
          : level === 2
            ? "mt-8 mb-2 font-heading text-xl font-bold"
            : "mt-5 mb-2 text-base font-bold";
      blocks.push(
        <Tag key={i} className={cls}>
          {inline(heading[2], i)}
        </Tag>,
      );
      i++;
      continue;
    }
    if (line.trim().startsWith("|")) {
      const rows: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
      const [head, , ...body] = rows;
      blocks.push(
        <div key={i} className="my-4 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr>
                {cells(head).map((c, j) => (
                  <th key={j} className="border-b-2 border-line px-2 py-2 align-bottom font-bold">
                    {inline(c, j)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>
                  {cells(r).map((c, j) => (
                    <td key={j} className="border-b border-line-soft px-2 py-2 align-top">
                      {inline(c, j)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && lines[i].trim() && !/^#/.test(lines[i])) {
        if (/^\s*[-*]\s+/.test(lines[i])) items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        else items[items.length - 1] += ` ${lines[i].trim()}`;
        i++;
      }
      blocks.push(
        <ul key={i} className="my-3 list-disc space-y-1.5 pl-6">
          {items.map((it, j) => (
            <li key={j}>{inline(it, j)}</li>
          ))}
        </ul>,
      );
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|\s*[-*]\s|\|)/.test(lines[i])) para.push(lines[i++].trim());
    blocks.push(
      <p key={i} className="my-3 leading-relaxed">
        {inline(para.join(" "), i)}
      </p>,
    );
  }
  return <Fragment>{blocks}</Fragment>;
}
