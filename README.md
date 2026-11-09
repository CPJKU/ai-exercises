# AI Exercises – Heuristic Search

In this notebook, you will implement a few heuristic search algorithms and apply them to  planning journeys in the Vienna public transport network and sliding puzzles.

## Run it online

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/CPJKU/ai-exercises/topic02?urlpath=lab%2Ftree%2Fheuristic_search.ipynb) [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/CPJKU/ai-exercises/blob/topic02/heuristic_search.ipynb)

Click a badge to open the notebook in your browser, without installing anything. Starting may take a few minutes. Your changes are **not saved** when the session ends: use *File > Download* to keep your work.

## Run it locally

Unpack the download (or clone this repository). You need Python 3.10 or newer. Set up an environment with either uv or conda:

**uv:**
```bash
uv venv
uv pip install -r requirements.txt
uv run jupyter lab
```

**conda:**
```bash
conda create -n ai-ue-02 -c conda-forge python=3.12 --file requirements.txt
conda activate ai-ue-02
jupyter lab
```

Then open `heuristic_search.ipynb` in JupyterLab.

## Data sources

The transit maps in `maps/vienna/` are derived from the Wiener Linien GTFS feed, published under CC BY (see `maps/vienna/SOURCE`). Related to notebook images, stored in `img` folder were AI-generated and provided under CC BY 4.0 (see https://creativecommons.org/licenses/by/4.0/legalcode.txt).
