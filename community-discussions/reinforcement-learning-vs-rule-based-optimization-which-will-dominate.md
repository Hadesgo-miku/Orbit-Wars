# Orbit Wars — Reinforcement Learning vs. Rule-Based Optimization — Which Will Dominate?

**Competition:** Orbit Wars

**Topic:** Reinforcement Learning vs. Rule-Based Optimization — Which Will Dominate?

**Posted by:** 寿!
**Position in competition:** 154th
**Posted:** a month ago

This competition represents a new type of task for Kaggle, and there aren't many past competitions we can draw on for reference. I'm not deeply familiar with optimization myself, but the problem feels closer to AHC (AtCoder Heuristic Contest) than to typical Kaggle competitions — AHC061 in particular comes to mind. Based on what I've seen from those contests, reinforcement learning is a viable approach, but due to its implementation complexity and other factors, it hasn't become the dominant strategy among top solutions. That said, AHC is a short-format contest attracting participants with strong algorithmic backgrounds, whereas Kaggle runs longer and draws more people with machine learning expertise — so the dynamics here may differ. My sense is that rule-based optimization is currently the mainstream approach, but where things will stand two months from now is anyone's guess. Where are you placing your bet — rule-based or RL? I'd love to hear your thoughts!

## Comments

### Sheeesh---
Posted a month ago · 65th in this Competition

A single top 1 RL will dominate. followed by 10 imitation learning bots learning from that bot xD

### 寿! — TOPIC AUTHOR
Posted a month ago · 154th in this Competition

Why can you say their bots are RL-based? I would think it's difficult to do effective RL in a short time frame. This is just meta-reading on my part, but some of the top players have high ratings on AHC. The fact that they're doing well leads me to think that optimization using algorithms mainstream in AHC might be the dominant approach here.

### Sheeesh---
Posted a month ago · 65th in this Competition

i meant in the end, not current top 1 player

### James McGuigan
Posted a month ago · 2350th in this Competition

Claude Code says

❯ what other rl algos might work here

● Your setup has three constraints that rule out most of the RL zoo:

Black-box fitness — game outcome isn't differentiable, no per-step reward signal available.
Expensive evaluation — ~20–30 s per game. Budget is measured in hundreds-to-thousands of games, not millions.
Small parameter count (~1.3k weights) — you're in the regime where sophisticated search algorithms are tractable.

What fits well, ranked by effort-to-reward:

Tier 1 — drop-in replacements for your (1+λ) ES

OpenAI-ES / NES (biggest win, smallest change)

Same infrastructure. Instead of best-of-λ, treat the λ perturbed evaluations as a natural-gradient estimate:
gradient ≈ (1/σ) · Σᵢ rank_weightᵢ · εᵢ
θ ← θ + lr · gradient

Every candidate contributes signal instead of 23 being thrown away. On problems your size, typically 5–10× faster convergence than (1+λ). Reference: Salimans et al., 2017 (OpenAI's paper). ~30 lines of code change.

CMA-ES (strongest classical choice for <10k dims)

Adapts both the step size σ and a full covariance matrix of the search distribution. Learns which weight directions matter and which don't, then samples anisotropically. Gold standard for black-box optimization in your parameter regime.

```text
pip install cma
import cma
es = cma.CMAEvolutionStrategy(theta_flat, sigma0=0.1)
while not es.stop():
    candidates = es.ask()
    scores = [evaluate(c) for c in candidates]  # parallelize
    es.tell(candidates, [-s for s in scores])    # cma minimizes
```

Caveats: default covariance-update cost is O(n²) per gen — at n=1.3k that's fine but noticeable. Use `CMAOptions({'CMA_diagonal': True})` for a diagonal approximation if it feels slow.

PEPG (Parameter-Exploring Policy Gradients)

Middle ground between NES and CMA-ES. Tracks a diagonal σ per parameter (so it knows to search more aggressively in flat directions). Simple to implement, good empirical record. Reference: Sehnke et al. 2010.

Tier 2 — refactor the scorer, unlock bigger methods

These all require turning the scorer from "deterministic real-valued ranker" into "stochastic policy." The planner already generates a candidate mission list per turn; you'd treat mission selection as a categorical action with logits from the NN.

REINFORCE with softmax mission selection

```text
logits = scorer.forward(mission_features)
probs = softmax(logits / τ)
chosen = sample(probs)
log_prob = log(probs[chosen])
```

At game end:

```text
loss = -sum(log_prob_t) * (return - baseline)
```

Gradient-based, so backprop through the NN per game. Much higher sample efficiency than ES on shaped-reward tasks. Needs:

- Per-turn logging of which mission was chosen and its log-prob
- A baseline (running average of returns) for variance reduction
- autograd or similar — your current NN is NumPy, would need a port to PyTorch/JAX (~200 loc)

PPO (if REINFORCE plateaus)

Adds trust-region clipping and advantage normalization. More robust than raw REINFORCE but significantly more moving parts. Only worth it once REINFORCE is working and noisy.

Direct policy optimization with margin as reward

Your margin-shaped `final_margin` is already a good dense reward. Pair with REINFORCE directly — no separate value network needed.

Tier 3 — population-level methods (for plateau-breaking)

Population-Based Training (PBT)

Train N agents in parallel with different σ / lr / weight init. Periodically copy the best agent's weights to the worst, perturb hparams, continue. Doubles as automatic hyperparameter search. Good for breaking out of ES local optima that single-run CMA-ES can get stuck in.

Coevolution / league play

Maintain a diverse population of opponents (snapshots from past generations) and evaluate against a mix each round. AlphaStar-lite. Useful once self-play saturates — stops you from overfitting to a single opponent profile. Requires the refresh-opponent pattern we discussed earlier, plus a sampling policy.

What not to try

- DQN / Q-learning: your "actions" (missions) are dynamically generated, not from a fixed set. Q-table/Q-network architecture doesn't fit.
- MCTS / AlphaZero: your hand-planner already does structured search. Bolting MCTS on top would be enormously complex and mostly redundant.
- Bayesian Optimization: works up to ~50 parameters; your 1.3k is too many.
- Genetic algorithms with crossover: usually underperforms modern ES variants on neural nets. Historical artifact.

My pragmatic recommendation

Progress in this order, stopping whenever results are good enough:

1. Swap (1+λ) → OpenAI-ES — 30 lines, probably a ~5× speedup on your existing setup.
2. If ES plateaus, try CMA-ES — `pip install cma`, ~50 lines of adapter code.
3. Only if both plateau, refactor to REINFORCE — this is a real engineering investment (torch port, per-turn logging, differentiable scorer) and only worth it if gradient signal materially beats black-box.

Want me to sketch the OpenAI-ES adapter against your current `train.py`?

### MarvinTMB
Posted 19 days ago · 2279th in this Competition

Its stupid. Game outcome is approximately differentiable.

### James McGuigan
Posted a month ago · 2350th in this Competition

I tried taking one of the public notebooks (Orbit Star Wars) then vibe coding with Claude Code to retrofit a (1+λ) RL algo with reward shaping based on how quickly it kills the opponenent. So far I have not been able to get RL to exceed the rules based score

### simmons1025
Posted 11 days ago · 130th in this Competition

Actions at time ( t ) will influence outcomes at ( t + \eta ) (the estimated arrival time of ships). This delay may make credit assignment difficult.

### Durga Kumari
Posted a month ago

Feels like rule-based will lead initially but RL might surprise later if someone cracks efficient training

### Semil_P
Posted a month ago · 2652nd in this Competition

I'm aslo looking RL-based one but due short time frame for model also effort to train it, I didn't have clarity how it can works

### thiendangnn63
Posted a month ago · 526th in this Competition

I’m currently using rule-based optimization but can’t think of any more features to improve upon anymore. I’m trying to do RL but not sure if it would work better. What is your approach?

### Roy Wei
Posted a month ago · 162nd in this Competition

@thiendangnn63 I'd recommend RL. Except for one game where the agent is paralyzed, it wins the rest of 2p games so far. If everyone uses heuristic, then they probably have derived their ideas from same public notebook and thus have similar weak spots. RL will allow you to exploit them.

### thiendangnn63
Posted a month ago · 526th in this Competition

thank you! do you recommend any RL notebooks as reference to start out with?

### Roy Wei
Posted a month ago · 162nd in this Competition

@thiendangnn63 To be honest, I had zero idea of what the mainstream RL pipeline looked like before entering the competition. Without giving away too much, I'd say I used a coding agent to build a PPO baseline first, then ran tests and debugged. That's what I've done so far. I saw @kashiwaba kindly build a tutorial already. I haven't checked it yet, but you can start there.

### thiendangnn63
Posted a month ago · 526th in this Competition

thanks again twin :) good luck with the competition

### 寿! — TOPIC AUTHOR
Posted a month ago · 154th in this Competition

I am also using a rule-based approach. I have reinforcement learning in my sights as well, but since it is unclear how much effort it would take to train a decent agent, I haven't been able to start on it yet.
