# Orbit Wars — Tooling: Visualizer, Cinema Mode, and Tournament Runner

**Competition:** Orbit Wars

**Topic:** Tooling: Visualizer, Cinema Mode, and Tournament Runner

**Posted by:** Matthew Huang
**Position in competition:** 441st
**Posted:** 6 days ago

Hi everyone,

I put together some local tooling for developing and testing Orbit Wars bots and figured I'd post it here in case it's useful to anyone.

## Highlights

- **Visualizer:** single self-contained HTML viewer per match. Predicts trajectories of planets, comets, and fleets, and displays key resource graphs to analyze bot performance.
- **Cinema mode:** automatically plays through a match and highlights key events.
- **Tournament harness:** runs N matches of the same lineup in parallel across different seeds, tabbed viewer with aggregate stats.
- **Bundler:** packs a multi-file bot into a single `submission.py` for Kaggle (helpers embedded as strings, so `from physics import ...` keeps working).
- **Optimizer:** source-to-source inlining + loop unrolling for the bundled submission, when you're fighting the per-turn timeout.
- **Campaign mode:** graph of territories with different `boardSize` / `sunRadius` / `cometSpeed` / etc. to stress-test bots beyond the default config.

Repo: https://github.com/MatthewWHuang/orbit-wars

Licensed PolyForm Noncommercial - free for use in the competition.

Good luck!

The Visualizer Cinema Mode An event in Cinema Mode Another event in Cinema Mode

## Comments

### Durga Kumari
Posted 4 days ago

Really polished work. The campaign mode for stress testing is a great idea.

### Navneet
Posted 6 hours ago

Cool rbit Wars Tool @matthewwh

### P.J Leek
Posted 2 days ago · 1214th in this Competition

really enjoyed the cinema mode 🔥

### Kamalnath_S
Posted 2 days ago

Really creative implementation. I liked the visual effects and concept.😊

### Gerar Del Toro
Posted 3 days ago · 150th in this Competition

Does it work directly after just only unzipping any submission and using folder path in run args?

### TonyK
Posted 5 days ago · 8th in this Competition

Can you add option to get visualization by kaggle link or path to replay.json, please?

### Matthew Huang — TOPIC AUTHOR
Posted 5 days ago · 441st in this Competition

I just added this - if you grab the latest version you should be able to watch a pre-existing replay using `python play_replay.py "<replay_url>"` now. Let me know if it works!

### TonyK
Posted 5 days ago · 8th in this Competition

Yes, it's working, but firstly got some problem because didn't use quotes "" around link Now it's much easier to analyse replays - that plots are awesome

### Noorudheen km
Posted 6 days ago · 2732nd in this Competition

amazing work
