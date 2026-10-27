# Design notes: aesthetic pass (2026-10-27)

Sources (SKILL.md + at most one referenced file each, read 2026-10-27 IST; repos checked real via the GitHub API):
- impeccable: github.com/pbakaus/impeccable @ d34c87e (owner Paul Bakaus, Apache-2.0): SKILL.md + reference/craft-floor.md
- taste-skill: github.com/Leonxlnx/taste-skill @ 12af471 (MIT): skills/taste-skill/SKILL.md
- ui-ux-pro-max: github.com/nextlevelbuilder/ui-ux-pro-max-skill @ 28b3b8d (MIT): .claude/skills/ui-ux-pro-max/SKILL.md
Nothing installed, nothing vendored. Design references (shadcn/ui zinc tokens; Magic UI number ticker) recreated in plain CSS/one anime.js call.

## Checklist (data/finance dashboard = impeccable "Operate" mode: precision and restraint over expression)
1. Refinement preserves: keep every label, number, layout and copy; only type, colour, borders, spacing change. (impeccable)
2. The brief wins over skill taste: 1px borders and a mono face for numbers stay, as the task card asks. (impeccable)
3. Contrast >= 4.5:1 for body and caption text in light AND dark; never gray-on-gray captions. (all three)
4. Colour never the only signal: LEAK/OK/UNCHECKED text badges stay next to the red/green tint. (ui-ux-pro-max)
5. One ground, one ink, one accent; accent on actions and links only; semantic tokens, not raw hex in components. (taste, ui-ux-pro-max)
6. Two typefaces at most: one UI sans + one mono reserved for numbers, code and data. (taste, impeccable)
7. Tabular figures wherever numbers align (metrics, tables, dataframes). (impeccable "browser surfaces", taste)
8. Few type sizes with clear steps; tighter heading scale; headings tracking no tighter than -0.04em. (taste, impeccable)
9. Spacing on one 8px scale: tight inside groups, larger between sections, more above a heading than below. (impeccable, ui-ux-pro-max)
10. Separate surfaces with a tone step or a 1px border, no resting shadows, no glows beyond a subtle hover hint. (taste, impeccable)
11. No gradients, gradient text, glass/blur, eyebrows, or coloured border-left > 1px. (impeccable, taste)
12. One authored motion moment for the whole app, transform/opacity only, ease-out, never loops. (impeccable, taste)
13. prefers-reduced-motion: show the final state with no travel. (all three)
14. Theme browser surfaces too: focus ring, text selection, link underline offset. (impeccable)
15. No horizontal scroll at 390px; tables wrap or scroll inside their own box. (ui-ux-pro-max)

## Conflicts noted
- taste-skill bans 1px outlined boxes, monospace outside code, and any hover glow; the task card pins shadcn 1px borders,
  a mono face for numbers and a subtle border glow, so the card wins (impeccable: "the brief wins"). Glow kept to a
  border-colour change on hover; no box-shadow at rest.
- taste-skill's motion layer (>= 8 moving elements, entrances on every section) is for marketing pages; it contradicts
  the card's "max 1 animation" and was not applied.
