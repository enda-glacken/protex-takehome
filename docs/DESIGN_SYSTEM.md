# Design system

The rules the prototype's interface follows, and where they live in code (`web/src/styles.css`, tokens in `:root`).
The direction was set from reference dashboards I collected: a neutral canvas, white rounded cards, ink-filled
navigation and buttons, large figures, one typeface and one accent. Nothing is copied from them; the accent, the
mark and the layouts are this prototype's own.

## Principles

1. **Chrome is neutral.** Ink, greys and white. If something in the interface is coloured, the colour means something.
2. **One accent, used for "look here".** Floor-tape yellow, taken from the tape that marks a dock floor.
3. **Colour is data.** Ink is work being done. Yellow is waiting or spare time, the thing to look at. Red is belt downtime. None is used for decoration.
4. **Figures first.** A card carries one figure, large, with a short label above and one line below.
5. **Say what cannot be done.** A control with nothing behind it says so when selected.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--page` | `#eeeeee` | Page background |
| `--panel` | `#ffffff` | Cards |
| `--surface-2` | `#f5f5f5` | Tiles and cards inside a card |
| `--line` | `#e4e4e4` | Rules and row dividers |
| `--ink` | `#0b0b0c` | Text, filled buttons, the current tab |
| `--ink-2` | `#4a4a4f` | Supporting text |
| `--ink-3` | `#8b8b90` | Captions and notes |
| `--accent` | `#f5c400` | Selection, the playhead, "person to spare", rank badges |
| `--accent-soft` | `#fff4c4` | Reserved for a soft highlight; not used at present |
| `--handling` | ink | People handling freight and freight moving, in every chart |
| `--moving` / `--waiting` | `#8b8b90` / accent | Moving is grey; waiting is the accent yellow |
| `--critical` | `#c2332f` | Belt downtime; high priority |
| `--r-card` / `--r-inner` / `--r-ctl` | 20 / 16 / 12 px | Cards / tiles / buttons, tabs and inputs |

## Type

One family, Outfit, at four weights (300 to 600). Size and weight carry the hierarchy; there is no second typeface.

| Role | Size and weight |
|---|---|
| Page title (camera name) | 40 px, 500 |
| Figure in a tile | 24 to 34 px, 500 |
| Card title | 20 px, 500 |
| Body | 14.5 to 16 px, 400 |
| Label, caption | 12.5 to 13.5 px, 400 |

Numbers use tabular figures wherever they line up in a column.

## Components

| Component | Rule |
|---|---|
| Card (`.panel`) | White, no border, 20 px radius, on the grey page |
| Tile (`.tile`) | Grey fill, no border: label, one figure, one line |
| Tabs (`.cam-tabs`, `.tabs`) | Pills. The current one is filled with ink |
| Primary button (`.primary`) | Ink fill, white text. One per card at most |
| Secondary button (`.quiet`, `.call`) | White, 1 px grey outline. A chosen call fills with ink |
| Text button (`.rename`, `.more-link`, `.ghost-btn`) | Ink text, underlined when it is a link |
| Status pill (`.pill`) | Green for connected; grey outline otherwise |
| Rank badge (Top actions) | Yellow circle with an ink numeral. The only accent on that card |
| Selected row or marker | Yellow bar or fill, never blue |

## Charts

- One idea per row, with its label beside it, so little needs a legend.
- Handling is ink on a grey "in view" area. Belt downtime is red on a grey track. Events are ink dots.
- In a set of bars only the one the title is about is red; the rest are grey.
- On the video the labels need to stand out against a busy picture: handling is a white box, moving a dashed white box, waiting a yellow box, each with its word on it.
- The chart palette is neutral plus one accent on purpose. It passes the colour-blind separation check; it does not pass the checks that expect every series to be a mid-tone colour, and yellow is low-contrast on white, so every bar carries a labelled legend.
- Every chart title states the conclusion; the note under it says what is plotted.
- No second axis, no stacked categories on the timeline.

## Wording

- "Belt downtime" for the measure, "belt stop" for one occurrence.
- "Minutes of crew time" for people's time added together.
- "Waiting", not "idle".
- Approximate figures say so in the line underneath ("on average").

## Not done yet

- No dark theme.
- Spacing is consistent by eye, not from a spacing scale in tokens.
- Earlier one-off styles are still in the stylesheet under the design-system layer; they should be folded into it.
