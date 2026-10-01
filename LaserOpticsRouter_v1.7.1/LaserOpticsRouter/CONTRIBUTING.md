# Contributing

LaserOpticsRouter focuses on quick optical layout, usable CAD placement and
transparent reference budgets. Contributions that improve reliability and
clarity are welcome. Detailed optical simulation is outside its scope.

Community support and review are best effort; there is no promised response time.

## Report a reproducible issue

Use the [GitHub issue tracker](https://github.com/AmLanz/LaserOpticsRouter/issues).

Include the add-in version, Fusion version/OS, document intent (Part, Assembly,
Hybrid or legacy), parametric/direct mode, a minimal command sequence, expected
behavior and actual result. For CAD placement, include local-axis/datum details
and whether the source is internal or externally linked. A simple asymmetric
test component is more useful than a large proprietary assembly.

Copy the diagnostic text from the palette after a build error. Review it before
sharing: it can contain local file paths or component names. Screenshots should
show the selected endpoint and its path, not just the command text.

## Make a change

Keep optical calculations in `core.py`; Fusion operations belong in
`fusion_backend.py`. Keep `schematic.js` and `schematic_svg.py` in agreement for overview/export
changes; the tests compare their optical symbols.
Preserve existing endpoint packets, route identities and component assignments (with the documented X-normal convention).
Document any intentional change in model assumptions or file behavior.

Run `python -m unittest discover -s tests -q` and `node --test tests/*.cjs`.
Add focused regressions for meaningful behavior changes. Native API changes
also need an explicit Fusion check covering cancellation, Undo, save/reopen and
source-part integrity. State which platforms and operations you actually tested.

Keep requests focused, describe the motivating problem, and attach evidence
that the change fixes it. Contributions are distributed under the project's
Apache-2.0 license.
