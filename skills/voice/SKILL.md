---
name: voice
description: >
  Writing voice calibration from studied authors. Accepts combinatorial
  voice arguments to blend multiple writer influences.
  TRIGGER when: user invokes "/voice" or asks to "write like", "in the
  style of", "voice of", "blend voices", or references a specific writer
  influence for their prose. Also when user asks to review writing for
  voice/tone/style quality.
  DO NOT TRIGGER when: user asks to humanize existing text (use humanize
  skill), write code, generate commit messages, or produce technical
  documentation where voice is irrelevant.
metadata:
  author: DROOdotFOO
  version: "1.0.0"
  tags: writing, voice, style, prose, editing
---

# voice

Calibrate your writing voice against studied authors. Each voice file captures what a specific writer does -- sentence rhythms, structural habits, rhetorical moves, what they avoid -- so you can apply those patterns to your own prose without losing your identity.

## How it works

Voice files in `voices/` are reference profiles, not imitation targets. The goal is never to sound like Chapman or anyone else. It's to borrow specific _moves_ -- a digression habit, a way of sitting with uncertainty, a paragraph rhythm -- and fold them into writing that's still yours.

## Usage

### Single voice

```
/voice chapman
```

Loads the Chapman voice profile. Apply his patterns where they improve the draft.

### Blended voices

```
/voice pg-startup+chapman
```

Loads both profiles. Where they agree (e.g., both favor short pivot sentences after longer ones), lean hard into that. Where they conflict (PG opens with a thesis, Chapman opens mid-thought), pick per-paragraph based on what the material needs.

### With intensity

```
/voice pg-startup:heavy chapman:light
```

Weight the influence. Heavy means structural and rhythmic borrowing. Light means just a few moves (e.g., borrow Chapman's habit of sitting with an uncertainty but not his digressive pacing).

### Review mode

```
/voice review chapman
```

Read the draft and flag where it diverges from the target voice. Don't rewrite -- annotate. "This paragraph is in briefing mode. Chapman would sit with this idea longer." "This aside is good -- Chapman-like productive digression."

## Adding a new voice

1. Read several thousand words of the writer's prose across different topics
2. Create `voices/<name>.md` following the template in [voice-template.md](voice-template.md)
3. Focus on _moves_, not _content_ -- what they do structurally, not what they believe
4. Include both what to borrow and what to avoid (every writer has tics)
5. Add 3-5 real passages as calibration anchors

## Applying voices to a draft

When rewriting with a voice profile loaded:

1. Read the full draft first. Identify which paragraphs are working and which feel flat, mechanical, or rushed.
2. Don't touch paragraphs that already have life. Voice calibration is for the dead spots.
3. Apply moves from the loaded profile(s) -- but only where they serve the material. A Chapman-style digression in a status table is wrong. A Chapman-style moment of uncertainty in a risk section is right.
4. Preserve the author's technical vocabulary and domain specificity. Voice is about rhythm, structure, and emotional register -- not word choice in technical passages.
5. After rewriting, read the full piece end-to-end. Flag any sections where the voice shift is jarring (the "stitching" problem). Smooth transitions between the author's natural voice and the borrowed moves.

## Available voices

| Voice       | File                                         | Best for                                                                                                            |
| ----------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Chapman     | [voices/chapman.md](voices/chapman.md)       | Essays, blog posts, anything that benefits from thinking-out-loud and productive digression                         |
| pg-early    | [voices/pg-early.md](voices/pg-early.md)     | Combative essays defending an unfashionable position; arguments that earn an abstract claim through a physical scene |
| pg-startup  | [voices/pg-startup.md](voices/pg-startup.md) | Instructional pieces, how-to writing, founder advice, any prose that lands on a portable imperative                  |
| pg-late     | [voices/pg-late.md](voices/pg-late.md)       | Philosophical / cultural essays, refinement-driven arguments, pieces that show the writer changing their mind        |

## What You Get

- A calibrated writing voice applied to your draft, borrowing specific structural and rhythmic moves from loaded voice profiles
- In review mode, annotated feedback showing where your prose diverges from the target voice without rewriting it
- Blended voice configurations that weight multiple influences (heavy/light) per-paragraph based on what the material needs

## Reading guide

| Task                                | Read                                         |
| ----------------------------------- | -------------------------------------------- |
| Voice profile template              | [voice-template.md](voice-template.md)       |
| Chapman voice profile               | [voices/chapman.md](voices/chapman.md)       |
| Paul Graham early (2001-2004)       | [voices/pg-early.md](voices/pg-early.md)     |
| Paul Graham startup-era (2005-2015) | [voices/pg-startup.md](voices/pg-startup.md) |
| Paul Graham late (2016-present)     | [voices/pg-late.md](voices/pg-late.md)       |
