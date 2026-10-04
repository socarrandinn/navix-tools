# Navix Tools identity

Navix combines **navaja**, Spanish for pocketknife, with a technical suffix.
Two broad blades fan out from one compact, rounded handle: one home for
multiple utilities. The open pivot anchors the folding-tool idea, while the
fan suggests tools expanding from a dock. The symbol stays independent of
IP networking so future tools, including an AI usage meter, fit the identity.
There is no cross, shield, lettering, or fine decorative detail in the mark.

## Files

- `navix-mark.svg`: full-color symbol; square `0 0 256 256` viewBox.
- `navix-logo.svg`: horizontal lockup; `0 0 640 256` viewBox, bold Navix
  and small, letter-spaced TOOLS. Uses `Segoe UI, sans-serif` live text.
- `navix-mark-mono.svg`: one compound path filled with `currentColor`;
  transparent pivot and background, no gradients.
- `navix-brand-guide.png`: brand guide with the glossy app icon (light and
  dark tiles, sizes, monochrome marks and lockups).
- `navix-1024.png` / `navix-256.png`: glossy app icon on its dark rounded
  tile, taken from the brand guide; transparent corners.
- `navix.ico`: the same app icon for Windows (exe, installer, window and
  tray), with 16, 24, 32, 48, 64, 128 and 256 pixel images.
- `preview.png`: color mark on light and dark backgrounds, including
  actual-size 16, 24, 32, and 48 pixel samples.

## Palette

| Role | Hex |
| --- | --- |
| Handle gradient start: indigo | `#5145CD` |
| Handle gradient end: deep teal | `#167C94` |
| Diagonal blade: blue | `#5685F4` |
| Upright blade: teal | `#14B8A6` |
| Suggested dark surface / light-background wordmark | `#111827` |
| Suggested light surface / dark-background wordmark | `#F4F6FA` |

The handle gradient runs from upper left to lower right. Both blades use
solid colors to keep the small icon simple. Surface colors are suggestions;
all delivered icons have transparent backgrounds. On variable glass or
busy backgrounds, use the monochrome mark in a contrasting color or place
the color mark on a quiet surface.

## Usage

- **Minimum symbol size: 16 × 16 pixels.** Prefer 24–32 pixels for dock
  buttons. The silhouette carries recognition at 16 pixels; the pivot
  becomes a small antialiased opening. Do not add details or strokes.
- **Minimum complete lockup width: 240 pixels.** Below that width use the
  symbol alone so TOOLS remains readable.
- Preserve aspect ratio and the SVG's built-in padding. Allow at least
  another 16 symbol units of clear space around the outside of the viewBox.
- The lockup wordmark and mono mark use `currentColor` (black by default).
  For inline SVG, set CSS `color` to `#111827` on light surfaces or
  `#F4F6FA` on dark surfaces. An SVG loaded as an external image does not
  inherit its parent's CSS color; set `color` on the SVG root when making
  a themed copy. For Qt, set the SVG root color before rendering; do not
  rely on automatic widget-palette inheritance.
- Use the ICO with `QIcon` for the application/window icon. For tray icons,
  render the monochrome SVG in a color appropriate to the actual tray
  background. The provided ICO contains the full-color mark.
- Segoe UI is the intended Windows wordmark font. Other platforms can
  substitute their sans-serif font; outline the text before production
  print work if identical letterforms across systems are required.
- Do not stretch, rotate, add shadows, or put the mark inside a shield.

## Export and validation

Exports were generated with the project's PySide6 Qt SVG renderer at
1024 × 1024, then downsampled with Pillow using Lanczos filtering. Pillow
packaged the seven ICO resolutions. No dependency installation was needed.
SVGs were parsed as XML and accepted by Qt's SVG renderer. The color mark
was visually checked on light and dark surfaces at small sizes; ICO image
dimensions were verified programmatically.
