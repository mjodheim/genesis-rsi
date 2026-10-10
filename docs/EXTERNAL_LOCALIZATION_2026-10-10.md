# Localizers scored on projects they never saw — 10 October 2026

General RSI remains the objective, not an achieved result. Every fault localizer of this
repository was written, selected and validated on bugs of the seventeen Defects4J projects.
The development cases are all assigned, and their validation part has been scored three
times. This report covers a second, independent source of cases and the first use of it.

## What was built

GrowingBugRepository (revision `f198b74b…`, MIT licence) lists bugs of other projects in the
Defects4J format: a fixed revision, the source patch back to the buggy version and the
report of the failing tests. `experiment/bench/EXTERNAL_LOCALIZATION_V1.json` (digest
`584cef56…`) freezes what is eligible:

- a project is left out when it shares its name, its repository or any revision with the
  development catalogue, and one known copy of the Defects4J Math bugs is left out by name;
- at most 12 bugs per project, chosen by a hash of their name, so that two large projects do
  not dominate;
- each repository falls in one part by a hash of its address: 298 cases *first*, 273
  *second*, 173 *reserve*. Modules of one code base never sit in two parts. The reserve is
  not prepared.

A case is built without compiling anything: the source and test directories of the fixed
revision are extracted from a clone, the source patch is applied, and the edit sites are
read from the patch exactly as for the development cases. Sources stay outside the
repository; the sealed files hold names, revisions and digests.

## Trial EXTERNAL1

The plan (`experiment/external/EXTERNAL1/PLAN.json`, digest `bd3a8e74…`) was committed and
pushed before any module ran on these cases. Of the 298 cases of the first part, 293 were
prepared (five bugs of one project edit no file of the recorded source directory): 77
projects, 67 repositories. Two questions, each a paired comparison scored once:

| localizer | development validation (211) | external, first part (293) |
|---|---|---|
| seed of the lineage (`g0`) | 43 | 63 |
| champion of LOCALIZER1 (`g3a3`), model-written | 88 | 134 |
| champion of LOCALIZER2 (`g3a3`), model-written | — | 130 |
| composite `c-31542d6f64b6`, built without a model | 93 | 155 |

- **Lineage.** The champion localizes 75 cases the seed misses and loses 4 (one-sided sign
  test below 1e-17). 41 projects show a net gain, 3 a net loss. The gain of the lineage is
  not specific to the projects it was developed on.
- **Recombination.** The composite localizes 29 cases its parent misses and loses 8 (sign
  test 0.0004). 22 projects show a net gain, 5 a net loss, 1 is level. On the development
  validation cases this gain was 13 against 8 and not established; it is established here.

No module failed on any case. No model was called.

## Limits

- One catalogue, Java only, and a catalogue built by its authors in the image of
  Defects4J: the cases are new projects, not a new kind of problem.
- The measure is localization within a window, not repair. These projects cannot be built
  in the present validator, so no repair trial can run on them.
- The composite was chosen once, by a hand-written merge rule. Nothing here shows a chain
  of model-free improvements.
- The first part is now consumed for these four localizers.

## What this establishes and what it does not

Established: both steps taken so far on the localizer, the model-written lineage and the
model-free composite, hold on 77 projects that took no part in their development, with a
paired gain in each case. The repository now has an independent source of cases with two
parts still unscored.

Not established: that better localization repairs more bugs (the paired repair trial of
9 October was level), or that Genesis improves its own machinery over several generations.

## Reproduction

```
git clone --filter=blob:none --sparse https://github.com/liuhuigmail/GrowingBugRepository.git G
git -C G checkout f198b74b03c1a12b4acd842a7d6568fe5efdbf9a
git -C G sparse-checkout set --no-cone '/framework/projects/*/active-bugs.csv' \
    '/framework/projects/*/patches/*.src.patch' '/framework/projects/*/trigger_tests/*' \
    '/framework/projects/*/dir-layout.csv' '/framework/bug-mining/bug_mining_projects_info.txt'
python3 scripts/run_external_localization.py prepare --source G --workspace W --part first
python3 scripts/run_external_localization.py score   --workspace W --name EXTERNAL1
```

Sealed result: `experiment/external/EXTERNAL1/RESULT.json`, digest `1d3a4680…`.
6 focused tests pass.
