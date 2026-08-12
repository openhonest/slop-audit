Licensing scope and additional terms
====================================

Copyright 2026 Adam Zachary Wasserman
SPDX-License-Identifier: Apache-2.0

The code and methodology in this repository are licensed under the Apache
License 2.0; the full, unmodified text is in LICENSE. This file carries the
scope statement and the additional terms that were previously stated in the
same file, reproduced below without alteration.

Why they are now in two files: licence detectors match canonical licence text,
so a summary carrying extra clauses matched nothing. GitHub reported this
repository as NOASSERTION ("Other") and every registry recorded it as
unlicensed. Nothing about the licensing changed; only which file states it.

NEEDS REVIEW (noted 2026-08-12, not acted on)
---------------------------------------------

The scope section below was written for the `aic-coe` repository and carried
over. Five of the six directories it names do not exist here:

    methodology/                        ABSENT   (this repo has no such directory)
    curriculum/                         EXISTS
    governance/                         ABSENT
    track-a-cpc-package/                ABSENT
    track-b-delivery-kit/               ABSENT
    track-c-administrator-enablement/   ABSENT

This repository actually contains: curriculum/, dimensions/, papers/, tools/,
validation/. So the scope statement describes a layout that is no longer the
one it governs, and the proprietary and governance carve-outs point at nothing.

That is a question about what the terms should cover, not a formatting problem,
so the text is left exactly as it was rather than being quietly corrected. It
needs a decision from the copyright holder.

Original text, unaltered
------------------------

## Scope of this license

This license applies to all files in the `methodology/` directory of the
aic-coe repository, including:

- `slop-audit-methodology.md` (the methodology document)
- Any reference scripts, audit tooling, or supporting code added later
- Any annexes, appendices, or supplementary documents added later

## What this license permits

- Use, modify, and redistribute the methodology, in whole or in part
- Build commercial products and services on top of the methodology
- Adapt the methodology for use in other domains or other audit contexts
- Translate the methodology into other languages
- Cite the methodology in academic and commercial publications

## What this license requires

- Attribution to Adam Zachary Wasserman as the original author
- Preservation of the Apache 2.0 license notice in any redistribution
- A NOTICE of any modifications made to the original
- The patent grant clause of Apache 2.0 (which protects users from patent
  litigation by contributors)

## What this license does not cover

- The **Honest trademark** and the **Certified Honest Practitioner** mark are
  not licensed under Apache 2.0. They are held by the Honest Foundation and
  licensed only by written agreement. See `governance/README.md` for details.
- The **curriculum** that teaches this methodology is in `curriculum/` and is
  released under CC-BY-NC-4.0, not Apache 2.0.
- The **commercial materials** in `track-a-cpc-package/`,
  `track-b-delivery-kit/`, and `track-c-administrator-enablement/` are
  proprietary and not released under any open license.

## Why Apache 2.0

The methodology is released under Apache 2.0 (rather than MIT, BSD, or a
permissive Creative Commons license) for two reasons:

1. **Patent grant.** Apache 2.0 includes an explicit patent grant from
   contributors, which protects downstream users from patent claims by
   anyone who has contributed to the methodology. This matters because
   the methodology is operationalized through tooling that may eventually
   intersect with patent claims in adjacent areas.

2. **Recognized in regulated procurement.** Apache 2.0 is the most widely
   accepted open-source license in regulated enterprise procurement,
   including in financial services, healthcare, and government. Releasing
   the methodology under a license that procurement teams already know
   reduces friction for the very organizations the methodology is designed
   to serve.
