from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent

st.set_page_config(page_title="Player profiles", page_icon="🎾")


def load_css():
    """Inject the tennis theme from style.css (one folder up from this page)."""
    css = (ROOT / "style.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def section(title):
    st.markdown(
        f'<div class="section-title" role="heading" aria-level="2">{title}</div>',
        unsafe_allow_html=True,
    )


# Display names for the stat columns
LABELS = {
    "aces": "Aces",
    "first_in": "1st serve in",
    "first_won": "1st serve points won",
    "second_in": "2nd serve in",
    "second_won": "2nd serve points won",
    "first_ret_won": "Return pts won vs 1st serve",
    "second_ret_won": "Return pts won vs 2nd serve",
    "winners": "Winners",
    "unforced": "Unforced errors",
    "net": "Net approaches",
    "net_won": "Net points won",
    "winners_fh": "Forehand winners",
    "winners_bh": "Backhand winners",
    "unforced_fh": "Forehand unforced errors",
    "unforced_bh": "Backhand unforced errors",
    "hard": "Hard",
    "clay": "Clay",
    "grass": "Grass",
}

GROUPS = {
    "Serve": ["aces", "first_in", "second_in", "first_won", "second_won"],
    "Return": ["first_ret_won", "second_ret_won"],
    "Groundstrokes": ["winners", "winners_fh", "winners_bh", "unforced", "unforced_fh", "unforced_bh"],
    "Net play": ["net", "net_won"],
    "Win rate by surface": ["hard", "clay", "grass"],
}


@st.cache_data
def load_players():
    df = pd.read_csv(ROOT / "players.csv", index_col=0)
    df["birthday"] = pd.to_datetime(df["birthday"])
    today = date.today()
    df["age"] = df["birthday"].apply(
        lambda b: today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    )
    return df


def load_picked():
    if 'picks' in st.session_state.keys():
        return st.session_state['picks']
    else:
        return None


def pct(x):
    return f"{x * 100:.1f}%"


def stat_block(player, tour_avg):
    for title, stats in GROUPS.items():
        st.markdown(f"**{title}**")
        cols = st.columns(len(stats) if len(stats) <= 3 else 3)
        for i, stat in enumerate(stats):
            delta = (player[stat] - tour_avg[stat]) * 100
            if player[stat] != 0:
                if "unforced" in stat:
                    delta *= -1
                    effective_answer = 1 - player[stat]
                    flip = "inverse"
                else:
                    effective_answer = player[stat]
                    flip = "normal"
                cols[i % len(cols)].metric(
                    LABELS[stat],
                    pct(effective_answer),
                    f"{delta:+.1f}% to similar avg",
                    delta_color=flip
                )
            else:
                cols[i % len(cols)].metric(
                    LABELS[stat],
                    value=None
                )


def profile(player, tour_avg, picked_row):
    head_cols = st.columns([1, 3])
    with head_cols[0]:
        if pd.notna(player.get("logo")):
            st.image(player["logo"], width=110)
    with head_cols[1]:
        st.markdown(f"### {player['player']}")
        country = "" if player["country"] == "World" else f" · {player['country']}"
        if str(player["tour"]).startswith("F"):
            st.write(f"{player['tour']} #{int(player['ranking'])}{country}")
        else:
            st.write(f"{player['tour']} #{int(player['ranking'])}{country} · age {player['age']}")

        if picked_row is not None:
            notes = []
            if pd.notna(picked_row.get("strong_stat")):
                notes.append(f"**Standout stat:** {LABELS[picked_row['strong_stat']]}")
            if pd.notna(picked_row.get("weak_stat")):
                notes.append(f"**Weakest stat:** {LABELS[picked_row['weak_stat']]}")
            if pd.notna(picked_row.get("strong_surface")) and not str(player['tour']).startswith("F"):
                notes.append(f"**Best surface:** {picked_row['strong_surface'].title()}")
            if notes:
                st.caption(" · ".join(notes))

    stat_block(player, tour_avg)


def show_group(names, picked, players, tour_avgs):
    for n, name in enumerate(names):
        match = players.loc[players["player"] == name]
        if match.empty:
            st.warning(f"No data found for {name} in players.csv.")
            continue
        player = match.iloc[0]
        picked_row = picked.loc[picked["player"] == name].iloc[0]
        tour = player["tour"]
        with st.expander(f"{name} — {tour} #{int(player['ranking'])}", expanded=False):
            profile(player, tour_avgs.loc[player["bracket"]], picked_row)


load_css()

st.markdown(
    """
<div class="hero">
<div class="hero-title" role="heading" aria-level="1">Player profiles</div>
<p class="hero-text">Stats for your favourites and your latest recommendations. Stats are compared to similarly ranked players on the same tour.</p>
</div>
""",
    unsafe_allow_html=True,
)

players = load_players()
picked = load_picked()

if picked is None or picked.empty:
    st.info("No profiles yet. Go to the main page, add your favourite players and generate recommendations first.")
    st.stop()

stat_cols = [c for g in GROUPS.values() for c in g]
tour_avgs = players.groupby("bracket")[stat_cols].mean()

# get_picks() concatenates the favourites (no stat_offset) with the recommendations (which have one)
favourites = picked.loc[picked["stat_offset"].isna(), "player"].tolist()
recs = picked.loc[picked["stat_offset"].notna()].sort_values("stat_offset")["player"].tolist()

section("Your favourites")
show_group(favourites, picked, players, tour_avgs)

section("Your recommendations")
show_group(recs, picked, players, tour_avgs)

st.write("---")
st.caption("Includes data sourced from https://github.com/JeffSackmann/tennis_MatchChartingProject")
