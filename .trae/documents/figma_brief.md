Figma Design Brief: StudyNinja Roadmap UI

Scope

* Core map screen for learning roadmap with pan/zoom and graph nodes

* UI kit components for nodes, edges, HUD and tooltips

* Desktop and mobile adaptive concepts

Deliverables

* Page Map Desktop (1920x1080): expanded graph with active path

* Page Map Mobile (iPhone 13): simplified list/mini‑graph view

* Page UI Kit: nodes in 5 states, edge types, badges, progress bars

* Page Tooltip/Pop‑up: node details, entry actions, preview of P/M/C1/F1

* Page Prototype: interaction flow from node → lesson steps → C1/F1

Visual Principles

* Modern Tech/Sci‑Fi Light, clean but gamified

* Dark mode default with soft grid background

* Achievement feel on mastered nodes (gold/shine)

Node States

* Locked: grey, semi‑transparent, lock icon

* Available: accent color, subtle glow, “Start” CTA

* In Progress: circular loader or filled bar segments (I/We/You)

* Mastered: green/gold, checkmark, shine

* Critical Gap: red/orange, alert badge

Zoom Levels

* Bird’s eye: icon + title + status color

* Close up: expand node, show 3 branch indicators I/We/You with progress

Edges

* Directional flow (arrow/particles), thickness by priority

* Active path bold, side edges thin, semi‑transparent

HUD/Overlay

* Mini‑map (overview box)

* Target tracker (overall goal progress)

* AI helper avatar (context tips)

* Legend (colors and statuses)

Interaction Rules

* Hover: highlight node and connected edges, show mini tooltip

* Click: open details modal (actions: Start, Resume, Review, Boosters)

* Pan/Zoom: inertia, bounds, snap to active path on “Center”

Accessibility

* Color contrast AA, keyboard navigation for focusable elements

* Tooltip timings and motion reduce option

Assets to Prepare

* Node hex and squircle shapes, 5 color variants

* Edge markers, arrows, particles, path glow

* Progress ring and segmented bars

* Badges: lock, check, alert, booster

Data Hooks

* Node shows P/M/C1/F1 indicators when close up

* Roadmap integrates topic→skills→methods relations visually

Notes

* Align terms with docs/cluster\_spec.md

* Keep components as auto‑layout, styles linked to tokens

