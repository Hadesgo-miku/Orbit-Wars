# Orbit Wars — Sweep Logic and Visualizer Color Updates

**Competition:** Orbit Wars

**Topic:** Sweep logic and visualizer color updates

**Posted by:** Bovard Doerschuk-Tiberi, Kaggle Staff
**Posted:** 22 days ago

https://www.kaggle.com/competitions/orbit-wars/discussion/696043

The planet "sweep" logic contained an error that allowed fleets to overshoot, this has been fixed.

https://www.kaggle.com/competitions/orbit-wars/discussion/693541

Yellow/orange were too close together. The color pallete was chosen from a color-blind-friendly color palette and I switched to a darker orange option from that set.

Thank you to both @jademonk and @sonphamorg for reporting!

## Comments

### Ezra
Posted 22 days ago · 21st in this Competition

Many top-10 agents (including my own) are now losing ships to the sun/OOB. I am not seeing these losses locally and did not see them on previous days, so they are likely due to this or other recent changes.

### Wenchong Huang
Posted 21 days ago · 72nd in this Competition

Yes. My agent also misses targets because of the "sweep" logic update. I've updated my physics engine to fit the new environment.

### Vincent Schuler
Posted 21 days ago · 23rd in this Competition

Is the new version available in kaggle kernels ?

Because the environment version hasn't changed (it remains v1.0.9), and I cannot see the new fonction swept_pair_hit() in the code !

### Bovard Doerschuk-Tiberi — Kaggle Staff
Posted 20 days ago

Kernels is not current with the latest release (they have a much slower release cadence). You'll have to update to the latest release (1.29.1) by doing a !pip install kaggle-environments in the first cell in your notebook
