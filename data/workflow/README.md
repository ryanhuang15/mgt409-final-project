# Corrected synthetic revision

`revised/` is a reproducible successor to the fictional flawed filing. It
corrects PA003 and PA020 reported rates, PA011 current premium, PA020 proposed
factor and the overall claim. It supplies factor rationale, removes the unsupported
approval note and updates the narrative's portfolio claim. The corrected modeled
portfolio impact is 6.13187705256…%, versus the original 7.84443006136…%.

The revised package is a **new filing**, not a rewrite of the original review.
Its metadata scenario ID is `revised_flawed`. Use the three-file revision upload
from the flawed example or a live flawed review. `rates.xlsx` is an alternate rate
file; upload one rate file, not both. Regenerate the fixture with
`python -m scripts.build_revision_example` if the original examples are
deliberately rebuilt. This fixture and its narrative are wholly synthetic.
