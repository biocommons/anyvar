> This file was merged into this repo in PR #516, before the repo was transferred to the GA4GH organization. It should stay at the root of this repo.

# AnyVar History

AnyVar was conceived and prototyped by [Reece Hart](https://github.com/reece) in 2018 and placed in the [biocommons](https://biocommons.org/) organization. Reece received funding as a contractor from ClinGen, through [Heidi Rehm](https://github.com/heidirehm) and [Larry Babb](https://github.com/larrybabb), to work on the [Variation Representation Specification](https://vrs.ga4gh.org/) and the [vrs-python reference implementation](https://github.com/ga4gh/vrs-python/) on which AnyVar relies. By 2019, the AnyVar prototype could ingest [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) and provide variant registration and lookup services.

Development accelerated in 2025, when [Alex Wagner](https://github.com/ahwagner) and Larry began marshalling contributors who made valuable and extensive improvements to AnyVar's reliability, scalability, speed, and documentation. By November 2025, contributions from those groups dominated the repo, and Alex and Larry had become the de facto leads of the project. Alex and Larry also built new services that depend on AnyVar, including variant-level matching and MCP providers, and became the recognized contacts for that work with funding agencies. They requested deviations from the software development processes of the biocommons organization. Forking the project was deemed by all parties to be detrimental to the effort and would likely have adverse implications for the integrity of links in grants and other materials. Therefore, the biocommons Steering Committee agreed to transfer the repo to GA4GH for continued development and community benefit. In exchange for the transfer, the recipients agree to provide appropriate credit for AnyVar and for the biocommons tools on which it depends in publications, presentations, and websites.

## Sustaining the biocommons foundation

AnyVar is the most visible layer of a larger stack. Its usefulness depends on biocommons libraries such as [hgvs](https://github.com/biocommons/hgvs), [seqrepo](https://github.com/biocommons/biocommons.seqrepo), [UTA](https://github.com/biocommons/uta), and [bioutils](https://github.com/biocommons/bioutils), which are maintained by a small community of volunteers and contributors from several organizations. Those libraries are harder to fund than the applications built on them, yet every service built on AnyVar inherits their reliability, or their neglect.

We therefore ask that the AnyVar community treat these foundations as shared responsibilities:

- **Contribute upstream.** When AnyVar needs changes to a biocommons library, make them in that library through its community process. Forks for development are welcome; long-lived forks that diverge will fragment the ecosystem that AnyVar depends on.
- **Include the foundation in funding.** When proposals build on AnyVar, include support for the biocommons libraries it depends on, as budget, effort, or named collaboration.
- **Give credit.** Cite AnyVar's origins and the biocommons tools it depends on in publications, presentations, and websites.

AnyVar will be only as sustainable as the infrastructure beneath it.
