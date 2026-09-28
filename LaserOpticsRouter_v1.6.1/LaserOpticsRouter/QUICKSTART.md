# LaserOpticsRouter — quick start

For a new setup, choose **Hybrid Design** in Fusion. Existing Part/Assembly
documents offer **Switch to Hybrid & build**. This explicit action changes
intent when building; draft editing and preview leave it unchanged.

## Sketch → inspect → build → continue

1. In **Layout**, name the route and set **Source** position, direction, diameter,
   beam model and color. Distances are mm; angles are degrees.
2. Use **+ Add step** to choose a family and a useful preset. **Custom…** inserts
   a step and focuses its relevant Inspector control. Frequently repeated setup
   values move ahead of unused presets. On a new line/run, click the starter
   **p100** to choose its replacement. Cancel leaves it unchanged; a manually
   added or confirmed `p100` opens the usual Inspector.
3. Edit, label, move or duplicate steps. **Commands** edits the same sequence.
   It starts expanded and remembers your collapse choice while editing.
   Visual moves retain the identity of repeated calibrated parts.
4. Scroll/pinch to zoom the overview; drag to pan. **Fit** restores the full
   route. XY/XZ/YZ selects the projection. With the map focused, use +/−,
   arrow keys and 0. Click an optic to open its Inspector.
5. Choose the endpoint below the overview. Its full known contributing path is
   highlighted, including resolvable upstream saved routes. The displayed
   diameter is **at that endpoint**. A true zero in the ideal geometric model
   is explicitly identified as a focus. Unresolved upstream context is labeled.
6. Keep **Use assigned CAD in solid preview & build** off for simple planning
   optics. Choose components and their XYZ/rotation in **Defaults → Default
   optics & components**. New optics use that default; uncheck **Use default**
   in Inspector for an individual choice. Use **Preview this CAD only**
   to check one part with red/green/blue local X/Y/Z datum axes. See the
   [component guide](docs/COMPONENTS.md) before preparing source files.
7. Use **Live draft preview** for lightweight native beam/optic guides. **Solid /
   CAD → Preview** respects the global CAD option. Enable that option when
   ready to build assigned parts. Build shows progress and checks cancellation
   between native operations; one expensive Fusion call can still pause the UI.
8. **Build** keeps the window open; the next build replaces that same route.
   **New run** starts an independent route. Save the Fusion document.
9. In **Saved paths & endpoints**, highlight a route/path in the overview before
   choosing **Edit**. Use **Start new run here** at an endpoint or
   splitter port. The complete beam state follows that endpoint.

Built routes retain their chosen colors when the palette closes and when
connections change. Saved paths shows connection warnings without dimming the
model. Legacy clear beams are restored once on opening; normal routes need no
material updates. Closing removes only temporary preview graphics.

The overview uses optical symbols, not mechanical footprints. Prism dot/arrow
marks are a schematic reminder of orthogonal polarization directions, not a
polarization calculation. Toggle **Polarization reference** to hide them.

## Generic optics and colors

Add `g` for an unlisted optic, uncheck **Use default**, label it (for example BBO), and choose **disc**,
**cube**, or **ball**. The overview uses a line, square or circle respectively.
Set its nominal size, optional disc thickness, loss, signed GDD, refractive index
and effective glass length in Inspector. Defaults are lossless and zero GDD.

Choose **Outgoing beam color** to label a downstream section, or keep the
incoming color. Colors are red, blue, green, yellow, orange, purple and white.
They are display labels; changing color does not change modeled wavelength or
simulate nonlinear conversion. A generic optic has no focusing or refraction.

## Budget selection

Open **Budget & export**, choose draft or saved paths, and check the desired
contributions. Each receives an editable highlight color. The map uses that
color around the physical beam color, so shared sections can show both selections.

Each card's **Included commands / optics** or **Used in this sum** describes
exactly what is counted. If a continuation starts at a reflected splitter port,
a selected parent endpoint is resolved to that port: downstream transmitted
optics are excluded. Read the T/R annotation and encounter list. Disconnected
or incompatible choices are reported instead of silently added. Independent
paths can join by endpoint position and forward direction (0.001 mm / 0.001°).
A unique intermediate connecting path is included automatically with its own
color and optics list; select an intermediate explicitly if the connection
is ambiguous. This combines local budgets; it does not repropagate independent
beam envelopes.

Loss multiplies along a connected arm; GDD adds with its sign. Effective glass
length contributes (n − 1) × thickness to the geometric path. These are manual
reference budgets, not a material or polarization simulation.

## Short commands

| Example | Meaning |
|---|---|
| `p10`, `p50`, `p100` | Free-space distance |
| `l-100`, `l-50`, `l50`, `l100` | Lens focal length, with its sign |
| `r-90`, `r90` | Opposite azimuth turns |
| `r90f50`, `_r90f50` | OAP, incoming / outgoing parent-axis leg |
| `bsc`, `bsc-` | Cube with opposite reflected ports |
| `+bsc`, `-bsc` | Large / small cube; leading sign selects size |
| `wp20h`, `rp10.6v` | Wollaston / Rochon separation in the chosen plane |
| `bd4h p50 _bd4h` | Split and recombine an aligned displacer pair |
| `g` | Generic placeholder |
| `laha`, `laqu` | λ/2 and λ/4 passive waveplates |
| `nd` | ND filter; adjustable example OD 1 / 90% loss |
| `tp30d0.5` | 30° incidence from the normal; 0.5 mm parallel shift |
| `fr90` | CAD-only 180° rotation about local Z; same modeled beam turn |

For WP/RP/BD, `p` advances both active beams; other optics affect the main ray.
Use secondary endpoints for independently routed optics. The full syntax and
model conventions are in the [reference](docs/REFERENCE.md).

## Transmission displacement

For a +X beam, `tp30d0.5` tilts the normal toward +Y and shifts the outgoing
parallel ray +0.5 mm in Y. `tp-30d0.5` shifts toward −Y; a negative `d` reverses
the side. At zero angle, positive `d` is local left. This is a specified offset,
not Snell-law tracing, and it adds no geometric path length.

For `bs` and `bsc`, set **Transmitted displacement** in the global default or
uncheck **Use default** and set it on one optic. Positive shifts away from the
reflected branch; negative reverses it. The reflected ray always starts at the
original hit point. At 180° reflection, the fallback shift direction is local
right because the reflection plane is undefined. Zero preserves the old behavior.

The exported SVG matches the router's symbols, colors, grid and arrows; it is
an overview diagram with symbols not to scale, not a CAD drawing.

## Preserve work

- **Undo / Redo**, or Alt+Z / Alt+Shift+Z, changes the draft. Fusion Undo changes
  built geometry. Ctrl+Enter / Command+Enter previews a valid draft.
- Physical specification changes reset that step's local assignment; compatible
  orientation changes keep calibration. Ambiguous raw-text matches are reported.
- Recovery is saved after an editing pause. Restore/Discard is offered when
  reopening the same document. Save the Fusion design and export CSV for records.
- **Beam update available → Refresh beam** preserves optics for a compatible
  changed source. **Disconnected** requires reviewing its start or layout.
- Assigned local components share geometry. Linked sources use Fusion's normal
  update controls. Inserted CAD is unselectable by default as a selection
  safeguard, not an absolute geometry lock.
- **About / Cite** provides author, license, independence notice and citation.
