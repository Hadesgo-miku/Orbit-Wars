# Orbit Wars — Some Considerations on Evaluating Targets

**Competition:** Orbit Wars

**Topic:** Some considerations on evaluating targets

**Posted by:** istinetz
**Position in competition:** 46th
**Posted:** 15 days ago

Very casual write up. Let's jump in.

## Consider this state of the board

It's the start of the game. Which neutral planet do we target? One way to do it would be to target the planets closest to us.

That is, of course, bad, as those are planets with income of just one and 20/22 ships defending them. Additionally, the inner one will be very far away by the time our ships reaches it.

What else can we do? We can target the planets with the biggest income.

That is also a bad idea. The planet with the biggest income has 72 defenders. By the time we have 73 ships saved up, we will have lost the game.

The other 2 candidates, though, are not so bad. 17 and 18 defenders respectively (yes, we can send a fleet to the 17 defender planet in the corner). If we target them, it's already a decent agent. We can do that by simply doing something like:

```text
target_planet_value = planet.income / planet.defenders * some_constant
```

If we just do some formula of `income / defenders`, we would choose targeting the 17 defender planet. However, the problem is that it's a bit further away - several turns of ship production lost. So we have to account for travel time as well.

To solve that, we will turn to a concept from economics - present value. Basically, we prefer 100 ships now, rather than 100 ships in 20 turns. In fact, we probably prefer 100 ships now rather than 120 ships in 20 turns.

So we define a constant: `GAMMA = 0.99`

and we say that our present value for a given planet is:

```text
pv = income + income * GAMMA + income * GAMMA^2 + income * GAMMA^3 ...
```

So we value the immediate income of a planet higher. Mathematically, we can simplify the formula above to just:

```text
pv = planet.income * (1 - gamma)
```

…which is a present value of 500 for a planet with income 5.

However, we need to add some complications for a more honest accounting. First of all, the game ends in 500 turns. Secondly, we will not own a given planet immediately - if a flight takes 20 turns, we need to start with the discounted income after 20 turns.

The formula then becomes:

```text
pv = planet.production * (gamma ** arrival_turn - gamma ** horizon) / (1.0 - gamma)
```

This is already quite good. You can get 1000 rating on the leaderboard with just that and some trajectory calculations.

However, we can do better yet.

---

Consider this board state. It's early game, 2 players. The game is about equal. Which planet do we target, as orange?

Notice that orange is targeting the planet on the side, with 26 defenders, sending a fleet with 27 ships.

Naively, this is not such a bad idea. The planet has decent income, not that many defenders. But blue is close by. He will just send a small fleet that arrives just after we conquer the planet, and there is nothing we can do to stop him.

So we have to account for danger as well.

The first thing I tried was just checking the three closest planets, and seeing how many of them were allied, enemy, or neutral. Just hardcode some gamma values for each possibility. Here is what the danger map looks like.

I tried that, defining some values for gamma that seemed good, and this was a shockingly good improvement - something like 50-80 elo points from that.

Next up, I tried some more gradient-based approach:

```text
danger_score = sum([planet.ships / distance * planet.owner for planet in planets])
```

It looks like so.

This was surprisingly bad. The first version lost 16 to 0 against the heuristic version above. Even after extensive sweeping on constants and variations of the formula, best I could do was achieve parity with the stupid heuristic version above.

Finally, I tried to calculate the danger as the proportion of ally strength to enemy strength.

I.e.

```text
ally_strength = constant + sum of ally planet ships / distances
enemy_strength = constant + sum of enemy planet ships / distances

danger = ally_strength / (ally_strength + enemy_strength)
```

This looks like so.

I think it's promising, but it's still losing a lot and I can't get it to work well.

That's all, let me know if you have any suggestions on what else we should try.

## Comments

### Gabriel MercierX
Posted 13 days ago · 957th in this Competition

Thanks for the insights, very interesting and nice visualizations ! For your gradient-based method, your visualization seems to be too sharp near planets and too flat far away, maybe you could parametrize it differently (like `planet.ships / (distance ** alpha)` with `alpha < 1` to tune, or `planet.ships * alpha ** distance` with `alpha < 1` again). And maybe the distance is not a good metric but the time to reach could be a better proxy (with `distance / fleet_speed(total_num_ships)` for example). Let me know what you think.

And how would you mix the planet_value score and the danger score ? With a tuned linear combination ? Or something like `pv * (1 - danger)` ?

### istinetz — TOPIC AUTHOR
Posted 12 days ago · 46th in this Competition

for your gradient-based method, your visualization seems to be too sharp near planets and too flat far away, maybe you could parametrize it differently (like `planet.ships / (distance ** alpha)` with `alpha < 1` to tune, or `planet.ships * alpha ** distance` with `alpha < 1` again).
I tried a few variations on the danger formulas. Nothing was natively great.

And how would you mix the planet_value score and the danger score ? With a tuned linear combination ? Or something like `pv * (1 - danger)` ?
I tried a mapping function over the danger, and moved ships where the danger was around 0.5 (equal pressure from allies and enemies), assuming that this is where the frontline is.

### Sammymatik
Posted 15 days ago · 494th in this Competition

Good write-up; i like your visualizer. It's fun to see everyone's visualizer… we should do a visualizer showcase thread… hahah :D

### Janek Đào
Posted 10 days ago · 1239th in this Competition

woah new invention tkss

### Navneet
Posted 12 days ago

Thanks for evaluating targets @istinetz

### Durga Kumari
Posted 10 days ago

Really cool approach using present value for planet evaluation is a clever idea.

### kgareth
Posted 12 days ago · 1562nd in this Competition

What does the horizon represent here?

The formula then becomes `pv = planet.production * (gamma ** arrival_turn - gamma ** horizon) / (1.0 - gamma)`

### istinetz — TOPIC AUTHOR
Posted 12 days ago · 46th in this Competition

The end of the game for the planets. For the comets, it's the turn they leave the game board.
