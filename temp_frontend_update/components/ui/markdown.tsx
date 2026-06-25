"use client"

import { Fragment } from "react"

// Minimal markdown renderer for AI research reports (headings, lists, paragraphs, bold).
function inline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i} className="font-semibold text-card-foreground">
        {p.slice(2, -2)}
      </strong>
    ) : (
      <Fragment key={i}>{p}</Fragment>
    ),
  )
}

export function Markdown({ content }: { content: string }) {
  const lines = content.split("\n")
  const blocks: React.ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null

  const flush = () => {
    if (!list) return
    const Tag = list.ordered ? "ol" : "ul"
    blocks.push(
      <Tag
        key={`l-${blocks.length}`}
        className={
          list.ordered
            ? "my-3 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground marker:text-primary"
            : "my-3 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-muted-foreground marker:text-primary"
        }
      >
        {list.items.map((it, i) => (
          <li key={i}>{inline(it)}</li>
        ))}
      </Tag>,
    )
    list = null
  }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) {
      flush()
      continue
    }
    if (line.startsWith("## ")) {
      flush()
      blocks.push(
        <h2 key={`h-${blocks.length}`} className="mt-6 text-lg font-bold text-card-foreground first:mt-0">
          {inline(line.slice(3))}
        </h2>,
      )
    } else if (line.startsWith("# ")) {
      flush()
      blocks.push(
        <h1 key={`h-${blocks.length}`} className="mt-6 text-xl font-bold text-card-foreground first:mt-0">
          {inline(line.slice(2))}
        </h1>,
      )
    } else if (/^[-*]\s/.test(line)) {
      if (!list || list.ordered) {
        flush()
        list = { ordered: false, items: [] }
      }
      list.items.push(line.replace(/^[-*]\s/, ""))
    } else if (/^\d+\.\s/.test(line)) {
      if (!list || !list.ordered) {
        flush()
        list = { ordered: true, items: [] }
      }
      list.items.push(line.replace(/^\d+\.\s/, ""))
    } else {
      flush()
      blocks.push(
        <p key={`p-${blocks.length}`} className="my-3 text-sm leading-relaxed text-muted-foreground">
          {inline(line)}
        </p>,
      )
    }
  }
  flush()

  return <div className="max-w-none">{blocks}</div>
}
