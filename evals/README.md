# Evals

Unit tests (`./run.sh test`) check that the code does what it says. Evals check that what it says is
**true of the video**. Two evals, both small enough to do by hand in a take-home.

## 1. Activity labels vs a human (`activity_labels.csv`, `score_activity.py`)

Pick 15 to 20 moments spread across the clip (include easy and awkward ones: occlusion, people
walking past, someone leaning on the belt). For each, pause the video and write down what you see:

    t_s,present,handling,note
    125,4,2,"two at belt end lifting, two standing by cages"

Then `./run.sh eval` prints agreement with the pipeline's `timeline` table: exact match rate and mean
absolute error for `present` and `handling`. Report the numbers in the README, whatever they are.
Label BEFORE looking at the pipeline's answer for that second.

## 2. Skill answers vs ground truth (`skill_questions.json`, `skill_ground_truth.py`)

`skill_ground_truth.py` computes the correct answer to each of the brief's four questions straight
from the store. Ask Claude the same questions through the skill and check each answer for:
the right time ranges, the right figure, a video link, and a stated confidence. Record pass/fail in
`skill_questions.json`.

A next step (not built): an LLM judge that grades the skill's answers against the ground truth
automatically, run on every change to `SKILL.md`.

## 3. Do the findings survive different thresholds? (`sensitivity.py`)

`python evals/sensitivity.py` re-runs the analysis on a temporary copy of the store, moving one
threshold at a time, and prints the headline figures for each variant. The real store and the web
data are not touched. Results are in the README under "Results on the reference clip".
