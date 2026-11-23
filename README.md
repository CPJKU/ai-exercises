# AI Exercises – Adversarial Search, Game Playing and Q-Learning

This notebook walks you through implementing algorithms for game playing and reinforcement learning. In the first part, you write **minimax** and **alpha-beta pruning** and use them to play tic-tac-toe. In the second part, you build a controller for an elevator: you implement **Q-learning** (the Q-table, ε-greedy action selection, the Q-update and the learning loop) and let the elevator learn to carry people around a building.

## Run it online

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/CPJKU/ai-exercises/topic03?urlpath=lab%2Ftree%2Fgame_playing.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CPJKU/ai-exercises/blob/topic03/game_playing.ipynb)

Click the badge to open the notebook in your browser, without installing anything. Starting may take a few minutes. Your changes are **not saved** when the session ends: use *File > Download* to keep your work.

## Run it locally

Unpack the download (or clone this repository). You need Python 3.11 or newer. Set up an environment with either uv or conda:

**uv:**
```bash
uv venv
uv pip install -r requirements.txt
uv run jupyter lab
```

**conda:**
```bash
conda create -n ai-ue-03 -c conda-forge python=3.12 --file requirements.txt
conda activate ai-ue-03
jupyter lab
```

Then open `game_playing.ipynb` in JupyterLab.

## Files

- `game_playing.ipynb` – the exercise notebook, with six `TASK` cells to fill in
- `search/tictactoe.py` – the tic-tac-toe game used for minimax and alpha-beta
- `search/searchtree.py` – draws the animations of the minimax and alpha-beta search trees
- `qlearning/elevator.py` – the elevator problem: states, actions, rewards and transitions
- `qlearning/drawing.py` – draws elevator states and Q-values as SVG, and the learning curve
- `qlearning/controllers.py` – runs a controller for an episode, and averages its cost over many episodes
- `qlearning/playground.py` – the interactive elevator at the end of the notebook

Training the Q-table takes about a minute or two. If you only want to check that your code runs, call `train(Q, episodes=50_000)` instead.
