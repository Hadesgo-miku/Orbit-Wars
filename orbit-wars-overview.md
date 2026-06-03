# Orbit Wars Overview

## Competition summary

Orbit Wars is a Kaggle competition focused on building and/or training AI bots for a novel multi-agent 1v1 or 4-player free-for-all real-time strategy game.

- **Game theme:** Conquer planets rotating around a sun in continuous 2D space
- **Players:** 2 or 4
- **Goal:** Submit bots that compete against other submitted agents on a ladder
- **Submission limit:** Up to 5 agents per team per day
- **Leaderboard policy:** Only the best scoring bot is shown on the leaderboard, but all submissions can be tracked on the submissions page
- **Latest submissions used for final evaluation:** Only the latest 2 submissions are tracked for final submissions

## Description

Welcome to Orbit Wars. Command the fleet. Conquer the void.

Orbit Wars brings back the strategic feel of the 2010 Planet Wars challenge with updated mechanics. Players launch swarms of ships across the solar system, outmaneuver opponents, and try to achieve orbital supremacy.

## Evaluation

### Matchmaking and ratings

- Each submission plays episodes against other bots with similar skill ratings
- Skill ratings increase with wins, decrease with losses, and move toward the mean on ties
- Every submission continues playing until the end of the competition
- Newer bots play more frequently to provide faster feedback

### Validation and skill model

- When a submission is uploaded, it first plays a validation episode against copies of itself
- If validation fails, the submission is marked as `Error`
- Successful submissions start with an initial rating of `μ0 = 600`
- Skill is modeled as a Gaussian distribution `N(μ, σ²)`
- `μ` represents estimated skill and `σ` represents uncertainty
- `σ` decreases over time as more information is collected

### Rating updates

- Winning increases your `μ` and decreases the opponent’s `μ`
- Drawing moves both players’ `μ` values closer to the mean
- Rating update magnitude depends on deviation from expected result and each submission’s uncertainty
- The score margin in a game does **not** affect rating updates

### Final evaluation

- Final submission deadline: **June 23, 2026**
- Additional submissions are locked after that date
- Games continue running for about two more weeks
- The final leaderboard is determined after that evaluation period

## Timeline

- **April 16, 2026** — Start Date
- **June 16, 2026** — Entry Deadline
- **June 16, 2026** — Team Merger Deadline
- **June 23, 2026** — Final Submission Deadline
- **June 24, 2026 to approximately July 8, 2026** — Continued game running until leaderboard convergence

All deadlines are at **11:59 PM UTC** on the corresponding day unless otherwise noted.

## Prizes

- 1st Place — $5,000
- 2nd Place — $5,000
- 3rd Place — $5,000
- 4th Place — $5,000
- 5th Place — $5,000
- 6th Place — $5,000
- 7th Place — $5,000
- 8th Place — $5,000
- 9th Place — $5,000
- 10th Place — $5,000

## How to Play Orbit Wars

### Overview

- Players start with a single home planet
- The board is a **100x100 continuous space** with a sun at the center
- Planets orbit the sun, comets move on elliptical trajectories, and fleets travel in straight lines
- Game length: **500 turns**
- Winner: player with the most total ships at the end
  - ships on planets
  - ships in fleets

### Board layout

- Origin: top-left
- Sun: centered at `(50, 50)` with radius `10`
- Fleets crossing the sun are destroyed
- Symmetry: all planets and comets are placed with 4-fold mirror symmetry around the center
  - `(x, y)`
  - `(100-x, y)`
  - `(x, 100-y)`
  - `(100-x, 100-y)`

### Planets

Each planet is represented as:

`[id, owner, x, y, radius, ships, production]`

- `owner`: Player ID `0-3`, or `-1` for neutral
- `radius`: `1 + ln(production)`
- `production`: integer from `1` to `5`
- `ships`: current garrison
- Starting ships are between `5` and `99`, skewed toward lower values

### Planet types

- **Orbiting planets:** orbit the sun if `orbital_radius + planet_radius < 50`
  - They rotate at a constant angular velocity of `0.025-0.05` radians/turn
  - Use `initial_planets` and `angular_velocity` from the observation to predict positions
- **Static planets:** planets farther from the center do not rotate
- Total planets: `20-40` planets, arranged as `5-10` symmetric groups of 4
- At least 3 groups are static, and at least one group is orbiting

### Home planets

- One symmetric group is randomly chosen as the starting planets
- In a 2-player game, players start on diagonally opposite planets (`Q1` and `Q4`)
- In a 4-player game, each player gets one planet from the group
- Home planets start with `10` ships

### Fleets

Each fleet is represented as:

`[id, owner, x, y, angle, from_planet_id, ships]`

- `angle`: direction of travel in radians
- `ships`: number of ships in the fleet, fixed during travel

### Fleet speed

Fleet speed scales logarithmically with size:

`speed = 1.0 + (maxSpeed - 1.0) * (log(ships) / log(1000)) ^ 1.5`

- `1` ship moves at `1.0` units/turn
- Larger fleets move faster, approaching the maximum speed of `6.0`
- Around `500` ships move at about `5`
- Around `1000` ships reach max speed

### Fleet movement

Fleets move in a straight line each turn at their computed speed. A fleet is removed if it:

- leaves the board
- crosses the sun
- collides with any planet

Collision detection is continuous over the full path segment, not just the endpoint.

### Fleet launch

Each turn, the agent returns a list of moves:

`[from_planet_id, direction_angle, num_ships]`

Rules:

- You can only launch from planets you own
- You cannot launch more ships than the planet currently has
- Fleets spawn just outside the planet’s radius in the chosen direction
- Multiple launches from the same or different planets are allowed in one turn

### Comets

- Temporary extra-solar objects that fly through the board on highly elliptical orbits around the sun
- Spawn in groups of 4, one per quadrant, at steps `50, 150, 250, 350, 450`
- Radius: `1.0`
- Production: `1 ship/turn` when owned
- Starting ships: random, skewed low, minimum of 4 rolls from `1-99`
- All 4 comets in a group share the same starting ship count
- Speed: configurable via `cometSpeed`, default `4.0` units/turn
- Comets appear in the planets array and follow normal planet rules
- When a comet leaves the board, it is removed along with any ships on it
- Comets are removed before fleet launches each turn, so you cannot launch from a departing comet
- The `comets` observation field contains group data, including paths and `path_index`

### Turn order

1. Comet expiration
2. Comet spawning
3. Fleet launch
4. Production
5. Fleet movement
6. Planet rotation and comet movement
7. Combat resolution

### Combat

When fleets collide with a planet, combat is resolved as follows:

- Arriving fleets are grouped by owner
- Ships from the same owner are summed
- The largest attacking force fights the second largest
- The difference in ships survives
- If the surviving attacker matches the planet owner, the ships are added to the garrison
- If the attacker is different from the planet owner, it fights the garrison
- If attackers exceed the garrison, the planet changes ownership and the leftover ships become the new garrison
- If two attackers tie, all attacking ships are destroyed

### Scoring and termination

The game ends when:

- Step limit reaches `500` turns
- Elimination leaves only one player or zero players with planets or fleets

Final score = total ships on owned planets + total ships in owned fleets.
Highest score wins.

### Observation reference

- `planets`: all planets including comets
- `fleets`: all active fleets
- `player`: your player ID
- `angular_velocity`: planet rotation speed
- `initial_planets`: planet positions at game start
- `comets`: active comet group data
- `comet_planet_ids`: IDs of planets that are comets
- `remainingOverageTime`: remaining overage time budget

### Action format

Return a list of moves:

`[[from_planet_id, direction_angle, num_ships], ...]`

- `from_planet_id`: planet ID you own
- `direction_angle`: angle in radians (`0 = right`, `pi/2 = down`)
- `num_ships`: integer number of ships to send
- Return `[]` to take no action

## Agent convenience

The environment exports named tuples for easier field access:

```python
from kaggle_environments.envs.orbit_wars.orbit_wars import Planet, Fleet, CENTER, ROTATION_RADIUS_LIMIT

def agent(obs):
    planets = [Planet(*p) for p in obs.get("planets", [])]
    fleets = [Fleet(*f) for f in obs.get("fleets", [])]
    player = obs.get("player", 0)

    for p in planets:
        print(p.id, p.owner, p.x, p.y, p.radius, p.ships, p.production)

    return []
```

## Configuration

- `episodeSteps`: `500`
- `actTimeout`: `1`
- `shipSpeed`: `6.0`
- `sunRadius`: `10.0`
- `boardSize`: `100.0`
- `cometSpeed`: `4.0`

## Getting started

- All instructions and starter kits are in the starter kit
- Read the competition specs carefully to understand this year’s design
- Install `kaggle-environments>=1.28.0`
- Install the Kaggle CLI
- Generate Kaggle API credentials if needed
- Accept the competition rules before submitting
- Use `kaggle competitions` commands to list, submit, inspect submissions, episodes, replays, logs, and leaderboard

## Citation

Bovard Doerschuk-Tiberi, Walter Reade, and Addison Howard. Orbit Wars. https://kaggle.com/competitions/orbit-wars, 2026. Kaggle.
