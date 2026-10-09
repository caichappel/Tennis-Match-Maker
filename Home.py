from pathlib import Path

import streamlit as st
import random
import pandas as pd
from utils.find_data import get_picks

st.set_page_config(page_title="Find your next favourite player", page_icon="🎾")


def load_css():
    """Inject the tennis theme from style.css (sits next to this file)."""
    css = (Path(__file__).parent / "style.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def section(title):
    st.markdown(
        f'<div class="section-title" role="heading" aria-level="2">{title}</div>',
        unsafe_allow_html=True,
    )


load_css()

if 'players' not in st.session_state.keys():
    st.session_state['players'] = pd.read_csv('players.csv')

if 'favourites' not in st.session_state.keys():
    st.session_state['favourites'] = [''] * 5

st.markdown(
    """
<div class="hero">
<div class="hero-title" role="heading" aria-level="1">Find your next favourite player</div>
<p class="hero-text">Choose the players you already follow, pick a tour, and get recommendations for who to watch next.</p>
</div>
""",
    unsafe_allow_html=True,
)

placeholders = st.session_state['players']['player']

section("Your favourites")

# Filled in below, once the add/remove buttons have updated the count
slot_display = st.empty()

add_col, remove_col = st.columns(2)

with add_col:
    if st.button("+ Add player (up to 5)"):
        if st.session_state['inputs'] <= 4:
            st.session_state['inputs'] += 1

with remove_col:
    if st.button("Remove last player"):
        if 'inputs' in st.session_state.keys():
            if st.session_state['inputs'] >= 1:
                st.session_state['inputs'] -= 1

chosen = st.session_state.get('inputs', 0)
slots_html = "".join(
    f'<span class="slot{" on" if i < chosen else ""}"></span>' for i in range(5)
)
slot_display.markdown(
    f'<div class="slots" role="img" aria-label="{chosen} of 5 favourite players chosen">'
    f'{slots_html}<span class="slots-count">{chosen} of 5</span></div>',
    unsafe_allow_html=True,
)

if 'inputs' in st.session_state.keys():
    for i in range(st.session_state['inputs']):
        st.session_state['favourites'][i] = st.selectbox(f"Favourite player {i + 1}", key=f"playerplaceholder{i}", options=placeholders)
    for i in range(5):
        if st.session_state['inputs'] < (i + 1):
            st.session_state['favourites'][i] = ''
else:
    st.session_state['inputs'] = 0

if st.session_state['inputs'] == 0:
    st.caption("Add your first player to get started.")

section("Your recommendations")

include_atp_wta = st.selectbox("Include ATP/WTA in recommendations", options=["Both ATP and WTA", "ATP only", "WTA only"])

if include_atp_wta == 'Both ATP and WTA':
    include_atp = True
    include_wta = True
elif include_atp_wta == 'ATP only':
    include_atp = True
    include_wta = False
else:
    include_atp = False
    include_wta = True

max_ranking = st.slider(label="Maximum Ranking", min_value=25, max_value=100, value=100)
max_age = st.slider(label="Maximum Age", min_value=20, max_value=50, value=50)

if st.button("Generate recommendations", type="primary"):
    if st.session_state['favourites'] == [''] * 5:
        st.warning("Add at least one player you're a fan of first.")
    else:
        st.session_state['ai_result'], st.session_state['picks'] = get_picks(st.session_state['players'], include_atp, include_wta, st.session_state['favourites'], max_ranking, max_age)

if 'ai_result' in st.session_state.keys():
    st.write(st.session_state['ai_result'])
    st.write("Head over to Player Profiles for a closer look at these players!")

st.write("---")
st.caption("Includes data sourced from https://github.com/JeffSackmann/tennis_MatchChartingProject")
