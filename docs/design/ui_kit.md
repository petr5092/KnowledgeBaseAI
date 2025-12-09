UI Kit: StudyNinja Roadmap

Files
- Tokens: `docs/design/tokens.json`
- Assets: `docs/design/assets/*`

Components
- Node Locked/Available/Progress/Mastered/Gap (base 128x128, squircle radius 24)
- Edge Active/Inactive (192x24, arrow marker)
- Badges: lock/check/alert/booster
- Progress indicators: ring or segmented bars (3 segments I/We/You)

Variants
- Node: state (Locked|Available|Progress|Mastered|Gap), size (S|M|L), theme (Dark|Light)
- Edge: type (Active|Inactive), thickness (Thin|Medium|Bold)

Styles
- Color tokens → fills/strokes
- Typography: Inter 16/12, weights 600/500

Import to Figma (manual)
1. Create pages: UI Kit, Map Desktop, Map Mobile, Tooltip, Prototype
2. Import SVG assets via File → Place image → select from `docs/design/assets`
3. Create components (Ctrl/Cmd+Alt+K), set variants for Node and Edge
4. Apply color/text styles using tokens mapping
5. Assemble Map Desktop: place nodes, link edges, add HUD overlay
6. Assemble Map Mobile: list view + mini‑graph
7. Build prototype: set interactions on nodes and CTA buttons

Notes
- Keep interactive layers separate to avoid nested interactive elements warning
- Prefer auto‑layout and constraints for responsive behavior
