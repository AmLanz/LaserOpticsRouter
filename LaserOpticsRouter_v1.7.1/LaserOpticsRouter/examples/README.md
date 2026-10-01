# Example routes

Use **Budget & export → Import CSV** to open an editable draft. Sources and
spectrum settings are included; no external CAD components are required.
Preview or Build after inspecting the route. SVGs are standalone schematics
with symbols not to scale. The 3D examples include XY, XZ and YZ projections.

| CSV | What to inspect |
|---|---|
| [oap_cylinder_3d.csv](oap_cylinder_3d.csv) | Requested 3D OAP/cylindrical relay ending in a Wollaston pair; 750 mm main path. |
| [compressor_sidebands.csv](compressor_sidebands.csv) | Two parallel 600 lines/mm gratings, four encounters, roof-mirror return; 780 / 800 / 820 nm recombine at one output. |
| [compressor_gaussian.csv](compressor_gaussian.csv) | Same compressor with 20 nm intensity FWHM, nine spectral samples and a Gaussian spatial beam. |
| [cylindrical_focus.csv](cylindrical_focus.csv) | Two cylindrical lenses at different planes; distinct horizontal/vertical line foci. 5 mm geometric source. |
| [reset_plates.csv](reset_plates.csv) | A lens, then 5 mm focused 50 mm ahead, then a 5 mm collimated reset. Chief ray and budgets continue. |
| [grating_central.csv](grating_central.csv) | One 800 nm ray at a 600 lines/mm grating, 30° incidence, order +1. |
| [grating_sidebands.csv](grating_sidebands.csv) | 770 / 800 / 830 nm boundary probes, 180 mm free propagation after the grating. |
| [grating_gaussian.csv](grating_gaussian.csv) | 800 nm centre, 40 nm intensity FWHM, nine samples over ±3σ, Gaussian spatial beam. |
| [displacer_pair.csv](displacer_pair.csv) | Split/recombine example. |
| [reference_budget.csv](reference_budget.csv) | Manual loss/GDD/glass example. |

## 3D relay

The source is a 5 mm collimated geometric beam at the origin along +X:

```text
p100 l50 p25 r90 p75 _r90f50 p50 r90v45 p100 cyl100h p200 cyl100h p50 r-90v-45 p100 wp20h p50
```

The main endpoint is approximately (−74.2404, −163.8050, 247.4874) mm. Both
cylinder power planes are local horizontal planes after the 3D fold. This
exact sequence is also available in the Reference tab.

## Four-encounter compressor geometry

```text
p100 +gr600a-45m-1h p150 +gr600a13.126795470828m-1h p150 r0v90 p10 r180v-90 p150 +gr600a-45m-1h p150 +gr600a13.126795470828m-1h p100
```

Use λ₀ = 800 nm, a 5 mm source along +X at (0,0,0), and either ±20 nm sidebands
or a Gaussian spectrum of 20 nm intensity FWHM with nine samples. `+` selects
50.8 mm gratings, keeping all sampled hits inside the illustrated aperture.
Start with **Reuse matching coplanar grating surfaces on return passes** enabled.

The first incidence is −45° and its outgoing β is 13.126795470828° for order −1.
The next incidence matches that β, so the second parallel grating cancels
angular dispersion. A two-mirror roof return lifts the beam by 10 mm and sends
it through both gratings again. The third/fourth encounters reuse the second/
first physical grating respectively. All wavelengths leave at (0,0,10) mm along
−X; central geometric length is 810 mm. The 780 nm and 820 nm sideband lengths
are approximately 808.192905 mm and 811.836941 mm. These wavelength-dependent
lengths are retained in the endpoints; pulse duration and GDD are not calculated.

The roof pair separates input and output in Z. XY therefore superposes the
forward/return paths; use XZ/YZ to see their 10 mm separation. Grating symbols
mark each encounter, while CAD contains two gratings. Change the source or
groove density and adjust both paired incidence angles together. Separate
independently angled return gratings will not automatically recombine the rays.

Importing CSV sets the complete source. The Reference-tab compressor button
sets 800 nm, a collimated geometric 5 mm beam and ±20 nm sidebands. Add lenses,
mirrors or cylinders after the train to continue all samples, or copy its
central endpoint into another route. Gaussian weights are relative spectral
intensity with peak 1, not fractions of total power.

For the single-grating examples, β ≈ −1.146° and central width ratio ≈ 1.15447.
Their samples also continue through any subsequent optics. In geometric mode
`resetd5finf` stays at 5 mm; a Gaussian reset has a flat wavefront at that plane
and diffracts afterward. The reset marker imposes an envelope boundary condition.

See [Optical reference](../docs/REFERENCE.md) for conventions and model limits,
and [Component preparation](../docs/COMPONENTS.md) before assigning CAD.
