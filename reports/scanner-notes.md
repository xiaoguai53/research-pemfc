# Scanner handoff

Agent: `/root/scanner`. Finished UTC: `2026-11-13T16:49:24.737998Z`. The initial start clock was not separately captured before source reading; the coordinator should use the actual host assignment event for its workflow record. Earliest captured clock during this scan: `2026-11-13T16:47:48Z`.

## Selection

- Tutorial ID `amphlett_reference`, module `amphlett`, source `repo/opem/Documents/Amphlett.ipynb` (Full Run cells65,67/69).
- Exactly one proposed tool: `opem_simulate_polarization`, directly bound to `opem.Static.Amphlett.Static_Analysis`.
- README lines805-807 and official `test/test_Amphlett.py` give supporting calls and numerical anchors.
- Native API reports can be generated in a unique output folder, preserving original CSV/HTML/OPEM files. Native numeric data already includes all three voltage losses.

## Source and execution contract

Pinned source: `https://github.com/ECSIM/opem`, `27d343fb966361a4e6cc99650241f651778fc50f`. Execute the actual official vector before implementation and preserve its driver, input, native result and provenance. Native Python driver execution is permitted for this documented API; no need to run notebook pip-install directives. If the separate notebook Plot section is selected, preserve its figures and include matplotlib in the environment rather than silently omitting them.

## Units and scientific caveats

T is K, l is cm, A is cm², pressures are species partial pressures in atm, current is A, and JMax is A/cm². The official PO2=1 example is not ambient-air operation. Stack V/P are returned; the loss arrays are per cell. The native sweep excludes its stop and caps it at A*JMax. Efficiency follows the upstream uF/HHV convention.

`Ph` follows `Power_Thermal_Calc` with `opem.Params.Eth=1.23`; label it as the native model output, never as a validated air-cooled stack heat-rejection estimate or fan requirement. The source does not model airflow, fan parasitic power, dynamic membrane hydration, or spatial temperature gradients.

## Source defects and wrapper checks

`opem.Functions.filter_lambda` mutates the input. For lambda<14 it actually sets23 while warning that it set14. Reject values outside the documented14..23 domain with an explicit error instead of allowing this silent scientific input change; do not patch the upstream algorithm. Pass a fresh dict to the source. Negative step and reversed ranges are normalized upstream; a wrapper can require an explicit increasing positive sweep to prevent misleading input repair. Zero step must be rejected because the source while loop would not advance. Finite values and at least two sweep samples are needed for meaningful native linear fit. Source warnings/errors can print even with PrintMode=False; redirect upstream output away from stdio protocol stdout.

## Deferred work

Air-cooled thermal/water control needs a dedicated source implementation and validation dataset. Experimental calibration/comparison needs actual measured data and a separately sourced/validated comparison workflow. The current selection is a static PEMFC baseline, not validated hardware performance or a completed air-cooled system simulator.
