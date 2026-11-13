# Third-party sources

## Paper2Agent

- Source: https://github.com/jmiao24/Paper2Agent
- Revision: `8c2d059165ef8cdcb70dbea76655b9c2b55b38e6`
- License: MIT, copyright (c) 2025 Jiacheng Miao.
- The entire upstream `skills/paper2agent/` folder is retained under `.agents/skills/paper2agent/` in the full research workspace. Its license is retained in that folder and at `third_party/Paper2Agent-LICENSE`. The conversion workflow, original paper-reading resources, and verification helpers belong to their upstream authors. Our domain skill and guides are additions. The runtime-only ZIP includes the MCP integration rather than the full skill workspace.
- Paper citation: Miao et al. (2026), *Reimagining research papers as interactive and reliable AI agents*, Nature. DOI: https://doi.org/10.1038/s41586-026-11044-y.

## OPEM

- Source: https://github.com/ECSIM/opem
- Revision: `27d343fb966361a4e6cc99650241f651778fc50f` (package metadata version 1.4).
- License: MIT; full notice retained as `third_party/OPEM-LICENSE`.
- The production wrapper calls `opem.Static.Amphlett.Static_Analysis` from the pinned, separately installed source. It does not reimplement the scientific model.
- Software citation: Haghighi, Askari, Hamidi and Rahimi (2018), *OPEM: Open Source PEM Cell Simulation Tool*, Journal of Open Source Software, 3(27), 676. DOI: https://doi.org/10.21105/joss.00676.
- Original Amphlett model references remain in OPEM's source documentation and should be cited when used for research.

Third-party dependencies retain their own licenses. This repository's MIT license applies to the new integration code and documentation, subject to these notices and any separately marked material.
