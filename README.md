<img src="assets/vogel-orange.svg" width="72" alt="Amon P. Lanz bird logo">

# LaserOpticsRouter

**Sketch an optical setup. Check its path. Place the hardware when ready.**

LaserOpticsRouter is a desktop Autodesk Fusion add-in for physicists and optics
engineers planning laser and optical setups. It combines a visual sequence
editor, a navigable schematic, approximate beam envelopes, reusable CAD optics,
and transparent length/loss/GDD bookkeeping.

**Version 1.6.1 · Apache-2.0 · Amon P. Lanz**

[GitHub repository](https://github.com/AmLanz/LaserOpticsRouter) · [Report an issue](https://github.com/AmLanz/LaserOpticsRouter/issues)

![Optical layout with passive optics, a tweaker plate and colored beam paths](docs/overview.svg)

*A standalone SVG exported by the router. Optic symbols are schematic;
beam geometry and the grid use millimetres.*

## What it does

- Edit a path visually or with compact commands. Insert useful presets, move
  or duplicate steps, and keep calibrated component assignments attached.
- Pan and zoom XY/XZ/YZ schematics with oriented optical symbols. Inspect an
  endpoint and highlight the complete known path contributing to its values.
- Sketch lenses, mirrors, OAPs, plate/cube splitters, polarizers, Wollaston and
  Rochon prisms, beam displacers, half/quarter-wave plates, ND filters, tweaker plates, and generic disc/cube/ball placeholders.
- Assign real components while planning with simple optics. Preview one
  assigned part with datum axes, then enable full CAD when needed.
- Follow saved endpoints and splitter ports. Compare selected path budgets
  with editable highlight colors and explicit included commands and optics.
- Export route CSVs, router schematic SVGs and all-document route archives.

This is a layout and planning tool. It does **not** replace Zemax or a detailed
optical solver. The geometric and simplified Gaussian models omit aberrations,
polarization evolution, material ray tracing, interference, nonlinear conversion
and mechanical collision checking. Prism symbols carry reference polarization
marks only. Loss, GDD and glass corrections are manually assigned estimates.

## Install or update

1. Extract the release ZIP to a permanent location. Keep the whole inner
   `LaserOpticsRouter` folder together, including its assets and interface files.
2. In desktop Fusion, open the **Design** workspace and
   **Utilities → Add-Ins → Scripts and Add-Ins**.
3. On **Add-Ins**, add the folder containing `LaserOpticsRouter.manifest`, then
   select **LaserOpticsRouter → Run**. Optional **Run on Startup** registers its
   command without opening the palette automatically.

For new setups, choose **Hybrid Design**. Existing Part/Assembly documents show
**Switch to Hybrid & build** because the generated route uses internal
components. The explicit action changes document intent inside the build
transaction; it does not change parametric/direct modeling mode. Draft and
preview leave document intent unchanged.

**Updating:** save your design, stop the add-in, and replace the **entire contents**
of its registered folder with this release. Keep the folder's name/location.
Restart Fusion, run the add-in, and check that its badge reads **1.6.1**.
See [Changelog](CHANGELOG.md) for release information.

Requires desktop Fusion on Windows or macOS. Fusion supplies Python and the
embedded browser; no pip/npm installation is required. The add-in has no
external service dependency. Linked CAD uses Fusion's own data workflow.

## A first route

```text
p100 l50 p25 r90 p75
```

With the default 5 mm collimated geometric source along +X, this places a
50 mm lens, a 90° fold, and an endpoint at **(125, 75, 0) mm**. The total path
is **200 mm**, and the endpoint diameter is **5 mm**. The ideal geometric focus
occurs earlier along the reflected leg.

1. Set source position, beam model, diameter and color.
2. Use **+ Add step**, choose a preset, then edit the selected step in Inspector.
   On a new line/run, click the starter **p100** to replace it with any step.
   **Commands** starts expanded for direct entry and can be collapsed.
3. Drag or scroll the overview; use **Fit** to return to the full route. Choose
   the measured endpoint below the overview to see its path and diameter.
4. Plan with **Use assigned CAD in solid preview & build** off. Assign parts in
   **Defaults → Default optics & components** and keep **Use default** checked
   in Inspector. Use **Preview this CAD only** for individual orientation checks.
5. **Build** keeps the palette open; the next build replaces that route.
   **New run** starts an independent route. Save the Fusion document. Built
   colors persist when the palette closes; connection warnings stay in Saved paths.

For an unlisted optic, add `g`, uncheck **Use default**, label it (for example “BBO”), choose disc/cube/ball,
and enter its reference loss/GDD/glass values. A source color or outgoing `g`
color is a visual label; it does not change wavelength or simulate conversion.

In **Budget & export**, check paths to assign highlight colors. Each selected
card lists the exact contribution used in the sum, including the correct
transmitted/reflected port and any trimmed parent prefix. Paths also join by
matching endpoint position and forward direction. Unique intermediate paths
are included and listed; ambiguous connections need an explicit selection.
In **Saved paths**, highlight a route or endpoint on its overview before editing.

## Reusable optics and passive plates

**Defaults → Default optics & components** holds each physical optic's component,
datum, XYZ offsets, rotations and reference properties. New optics start with
**Use default** checked. Uncheck it for an independent local choice; recheck it
to follow the global default. With no assigned default, the built-in shape is
used. Defaults belong to the active Fusion document; built routes retain their
saved calibration until deliberately changed/rebuilt.

All `bs` angles/signs share one plate-splitter default per size (`bs30` and
`bs-90`, for example). Optional splitter displacement is zero initially: only
transmission shifts, while reflection starts at the incoming hit point.

| Command | Planning behavior |
|---|---|
| `laha` | Half-wave plate, thin disc; manual loss/GDD/glass budget |
| `laqu` | Quarter-wave plate, thin disc; manual loss/GDD/glass budget |
| `nd` | Thicker ND disc; adjustable example OD 1 / 90% loss |
| `tp30d0.5` | Plate normal tilted 30°; outgoing parallel beam displaced 0.5 mm |

Waveplates and ND filters leave the beam envelope and display color unchanged.
Tweaker displacement is explicit, not calculated from refractive index. See
[the reference](docs/REFERENCE.md) for angle/side conventions. Gratings are
outside this release.

## Guides

| Guide | Contents |
|---|---|
| [Quick start](QUICKSTART.md) | Workflow, presets, navigation, generic optics and budgets |
| [Component preparation](docs/COMPONENTS.md) | Origin/axis conventions, single-part inspection, links, protection and build performance |
| [Optical reference](docs/REFERENCE.md) | Commands, coordinate conventions, beam models, endpoints and budgets |
| [Verification](TESTING.md) | Portable coverage and outstanding native Fusion acceptance checks |
| [Changelog](CHANGELOG.md) | Changes by release |

## Development and support

The optical planner is independent of Fusion. Run from this directory:

```sh
python -m unittest discover -s tests -q
node --test tests/*.cjs
```

The release passes **239 Python and 107 JavaScript tests**. These include API/DOM
doubles, not Fusion's native kernel or embedded browser. The schematic SVGs
were rendered and inspected separately. Native build, cancellation/Undo,
external-reference updates and platform UI checks remain listed in
[TESTING.md](TESTING.md).

Community support is **best effort**, with no guaranteed response time.
When reporting a bug, include the add-in/Fusion versions, document type,
minimal route, expected result and relevant diagnostic log. Remove private
paths or project information before sharing. See [Contributing](CONTRIBUTING.md).

## License and citation

Copyright 2026 **Amon P. Lanz**. Distributed under the
[Apache License 2.0](LICENSE); see [NOTICE](NOTICE).

This is an independent project and is not affiliated with,
endorsed by, or sponsored by Autodesk.

The software is provided “AS IS” under the Apache License 2.0, without warranties.
To the extent permitted by applicable law, Amon P. Lanz and contributors accept
no liability for losses or damages caused by use of the software, including
bugs or inaccurate results. Independently verify layouts and calculations.
Nothing in this notice excludes liability that cannot lawfully be excluded.

If the software contributes to your work, a citation is appreciated and optional:

> Amon P. Lanz (2026). *LaserOpticsRouter* (version 1.6.1). Computer software.
> [https://github.com/AmLanz/LaserOpticsRouter](https://github.com/AmLanz/LaserOpticsRouter)

[CITATION.cff](CITATION.cff) enables GitHub's citation action. A
[BibTeX entry](CITATION.bib) and **About / Cite** in the palette are also provided.
