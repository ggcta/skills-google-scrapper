// Humanist theme — Google Skills Scraper (backlog #5).
//
// Professional · humanist · modern. Inter (headings/UI) + Lora (body serif) +
// Fira Code (mono), terracotta accent. This is a Pandoc *Typst template*:
// Pandoc fills the placeholder variables from the Markdown and its YAML
// frontmatter (id, type, portal, url, scraped_date, ...) and drops the
// converted document into the body slot. Rendered via:
// pandoc --pdf-engine=typst --template=this.

#let accent = rgb("#DE7356")
#let ink = rgb("#1F0909")
#let muted = rgb("#6B6B6B")
#let hairline = rgb("#E3DDD5")
#let panel = rgb("#F6F3EE")

// --- helpers Pandoc's generated body may reference (keep so it compiles) ---
#let horizontalrule = line(start: (25%, 0%), end: (75%, 0%), stroke: 0.5pt + hairline)
#show terms.item: it => block(breakable: false)[
  #text(weight: "bold")[#it.term]
  #block(inset: (left: 1.5em, top: -0.4em))[#it.description]
]
$if(highlighting-definitions)$
$highlighting-definitions$
$endif$

// --- page & running header/footer ---
#set page(
  paper: "a4",
  margin: (x: 2.2cm, top: 2.4cm, bottom: 2.2cm),
  header: context {
    if counter(page).get().first() > 1 {
      set text(font: "Inter", size: 8pt, fill: muted)
      grid(
        columns: (1fr, auto),
        align: (left, right),
        upper[$type$$if(portal)$ · $portal$$endif$],
        [$title$],
      )
      v(-6pt)
      line(length: 100%, stroke: 0.5pt + hairline)
    }
  },
  footer: context {
    set text(font: "Inter", size: 8pt, fill: muted)
    line(length: 100%, stroke: 0.5pt + hairline)
    v(2pt)
    grid(
      columns: (1fr, auto),
      align: (left, right),
      [Google Skills],
      counter(page).display("1 / 1", both: true),
    )
  },
)

// --- typography ---
#set text(font: ("Lora", "Noto Sans"), size: 10.5pt, fill: ink, lang: "en")
#set par(justify: true, leading: 0.72em, spacing: 1.05em)
#show link: it => text(fill: accent)[#it]
#set list(marker: (text(fill: accent)[•], text(fill: accent)[◦]))
#set enum(numbering: n => text(fill: accent, weight: "bold")[#n.])

// Task-list checkboxes: Pandoc emits ☐ / ☒, whose glyphs aren't in the body
// fonts. Draw them instead — portable and on-brand (no symbol-font dependency).
#let checkbox(done) = box(
  width: 0.82em, height: 0.82em, baseline: 0.08em, radius: 2pt,
  stroke: 1pt + accent, fill: if done { accent } else { none },
)
#show "☐": checkbox(false)
#show "☒": checkbox(true)

// headings — Inter, level 2 in accent
#show heading: set text(font: "Inter", fill: ink)
#show heading.where(level: 2): it => block(above: 1.5em, below: 0.7em)[
  #set text(size: 15pt, weight: 700, fill: accent)
  #it.body
]
#show heading.where(level: 3): it => block(above: 1.1em, below: 0.4em)[
  #set text(size: 11.5pt, weight: 600)
  #it.body
]
#show heading.where(level: 4): set text(size: 10.5pt, weight: 600, style: "italic")
#show heading.where(level: 5): set text(size: 10pt, weight: 600, fill: muted)
#show heading.where(level: 6): set text(size: 10pt, weight: 600, fill: muted)

// code
#show raw: set text(font: "Fira Code", size: 9pt)
#show raw.where(block: true): it => block(
  width: 100%, fill: panel, inset: 9pt, radius: 4pt, stroke: 0.5pt + hairline,
)[#it]

// tables — banded, Inter header
#set table(inset: 7pt, stroke: none)
#show table.cell.where(y: 0): set text(font: "Inter", weight: 700, size: 9pt, fill: ink)
#show figure.where(kind: table): set figure.caption(position: top)

// blockquote (used for the "Description:" style callouts if any)
#show quote.where(block: true): it => block(
  width: 100%, inset: (left: 1em, y: 0.2em), stroke: (left: 2pt + accent),
)[#set text(style: "italic", fill: muted); #it.body]

// The Markdown title is the single level-1 heading; we render a proper title
// band from the frontmatter instead, so drop the body's duplicate H1.
#show heading.where(level: 1): it => none

// --- title band ---
#block(spacing: 0.55em)[
  #set text(font: "Inter", size: 9pt, weight: 600, fill: accent)
  #upper[$type$$if(portal)$ · $portal$$endif$$if(id)$ · \#$id$$endif$]
]
$if(title)$
#block(spacing: 0.45em)[
  #set text(font: "Inter", size: 25pt, weight: 700, fill: ink)
  $title$
]
$endif$
#block(spacing: 1.1em)[
  #set text(font: "Inter", size: 8.5pt, fill: muted)
  $if(scraped_date)$Fetched $scraped_date$$endif$$if(url)$ #h(0.5em)·#h(0.5em) #link("$url$")[source]$endif$
]
#line(length: 100%, stroke: 1.5pt + accent)
#v(1.1em)

// --- contents (only when the document has enough modules/steps) ---
#context {
  let mods = query(heading.where(level: 2))
  if mods.len() > 2 {
    block(breakable: false, below: 1.4em)[
      #text(font: "Inter", weight: 700, size: 11pt, fill: ink)[Contents]
      #v(0.35em)
      #set text(font: "Inter", size: 9.5pt)
      #outline(title: none, target: heading.where(level: 2), indent: 0.8em)
    ]
  }
}

$body$
