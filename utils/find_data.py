import requests
import pandas as pd
import numpy as np
import random
from datetime import date

from sklearn.preprocessing import StandardScaler

from openai import OpenAI

def get_data(url):
    response = requests.get(url)
    return response.json()

def get_picks(df, atp, wta, favs, max_ranking, max_age, OPENROUTER_API_KEY):
    
    players_alt = df.copy()

    # Creating up-to-date age column to replace the birthdays
    players_alt['birthday'] = pd.to_datetime(players_alt['birthday'])
    today = date.today()
    players_alt['age'] = players_alt.apply(lambda x: today.year - x['birthday'].year - ((today.month, today.day) < (x['birthday'].month, x['birthday'].day)), axis=1)
    players_alt = players_alt.drop(columns=['birthday'])

    # The favs list has a fixed size of 5. Missing players are present as empty strings so we need to remove them
    input_list = favs.copy()
    while '' in input_list:
        input_list.remove('')

    playing_stats = ['aces', 'first_in', 'first_won', 'second_in', 'second_won', 'first_ret_won', 'second_ret_won', 'winners', 'unforced', 'net', 'net_won', 'winners_fh', 'winners_bh', 'unforced_fh', 'unforced_bh']
    surfaces = ['hard', 'clay', 'grass']
    features = playing_stats + surfaces

    # Scaling players with respect to set ranking brackets (to prevent the top players from all looking too similar to each other)
    slices = [players_alt.loc[(players_alt['bracket'] == "ATPLEG")][features], players_alt.loc[(players_alt['bracket'] == "WTALEG")][features]]

    segment_a = [1, 10]
    segment_b = [11, 25]
    segment_c = [26, 50]
    segment_d = [51, 100]
    
    for segment in [segment_a, segment_b, segment_c, segment_d]:
        slices.append(players_alt.loc[(players_alt['tour'] == "ATP") & (players_alt['ranking'] >= segment[0]) & (players_alt['ranking'] <= segment[1])][features])
        slices.append(players_alt.loc[(players_alt['tour'] == "WTA") & (players_alt['ranking'] >= segment[0]) & (players_alt['ranking'] <= segment[1])][features])
        
    scalers = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    
    Xs = []
    
    for i in range(len(slices)):
        scalers[i] = StandardScaler()
        scalers[i].set_output(transform='pandas')
        X = scalers[i].fit_transform(slices[i])
        Xs.append(X)
    
    X = pd.concat(Xs)

    # Attaching the non-numerical data back on
    info_cols = ['player', 'tour', 'ranking', 'country', 'age']
    
    players_alt_scaled = pd.merge(players_alt[info_cols], X, left_index=True, right_index=True)
    
    players_alt_scaled['strong_stat'] = players_alt_scaled[playing_stats].idxmax(axis='columns')
    players_alt_scaled['weak_stat'] = players_alt_scaled[playing_stats].idxmin(axis='columns')

    players_alt_scaled['strong_surface'] = players_alt_scaled[surfaces].idxmax(axis='columns')
    players_alt_scaled['weak_surface'] = players_alt_scaled[surfaces].idxmin(axis='columns')

    allowed_tours = []
    if atp:
        allowed_tours.append("ATP")
    if wta:
        allowed_tours.append("WTA")

    # Remove excluded tours (ATP/WTA) and anyone in the input list
    player_selection = players_alt_scaled.loc[(players_alt_scaled['tour'].isin(allowed_tours)) & ~(players_alt_scaled['player'].isin(input_list))  & (players_alt_scaled['age'] <= max_age)]

    input_rows = []
    for player in input_list:
        input_rows.append(players_alt_scaled.loc[players_alt_scaled['player'] == player])

    # Calculate how far off each player is from the input players in each stat using Euclidean distance
    player_selection['stat_offset'] = 0

    for stat in features:
        player_selection[stat+'_mod'] = 0
        for row in input_rows:
            player_selection[stat+'_mod'] = player_selection[stat+'_mod'] + (player_selection[stat] - row[stat].sum()) ** 2
        player_selection['stat_offset'] = player_selection['stat_offset'] + player_selection[stat+'_mod']
        player_selection[stat+'_mod'] = np.sqrt(player_selection[stat+'_mod'])
    player_selection['stat_offset'] = np.sqrt(player_selection['stat_offset']) / len(input_list)

    # Find how different the player is from the input in their respective strongest and weakest stats
    player_selection["strong_diff"] = player_selection.apply(lambda x: x[x["strong_stat"]+"_mod"], axis=1)
    player_selection["weak_diff"] = player_selection.apply(lambda x: x[x["weak_stat"]+"_mod"], axis=1)

    # Scoring players with an even weighting to the total stat offset and ranking
    player_selection = player_selection[['player', 'tour', 'ranking', 'country', 'age', 'stat_offset', 'strong_stat', 'strong_diff', 'weak_stat', 'weak_diff', 'strong_surface', 'weak_surface']]
    player_selection['score'] = player_selection['stat_offset'] + (player_selection['ranking'] / (250 / player_selection['stat_offset'].max()))
    player_selection = player_selection.sort_values('stat_offset')

    # Uses the score to find 1 player from the same country as a favourite
    # World is excluded because this is given to players from Russia and Belarus, who should not have their nationality discussed
    # If all players are listed as World or there are no other compatriots in the dataset, there are only four recommendations
    input_countries = []
    for player in input_rows:
        if player['country'].iloc[0] not in input_countries and player['country'].iloc[0] != 'World':
            input_countries.append(player['country'].iloc[0])

    player_selection_country = player_selection.loc[(player_selection['country'].isin(input_countries)) & (player_selection['ranking'] <= max_ranking)].sort_values('score')

    if player_selection_country.shape[0] != 0:
        country_selection = player_selection_country.head(1)
        player_selection = player_selection.drop(country_selection.first_valid_index())
        picks = [country_selection.iloc[0]]
        country = True
    else:
        picks = []
        country = False

    if not country:
        bonus_segment = random.choice([segment_a, segment_b, segment_c])
    else:
        bonus_segment = []

    segment_d = [51, max_ranking]
    if max_ranking < 60:
        segment_c = [26, max_ranking]
        if max_ranking < 35:
            segment_b = [11, max_ranking]

    # Recommend one of the top two player from each of the 4 ranking brackets
    for segment in [segment_a, segment_b, segment_c, segment_d]:
        filt = player_selection.loc[(player_selection['ranking'] >= segment[0]) & (player_selection['ranking'] <= segment[1])]
        if filt.shape[0] > 1:
            random_pick = random.choice([0, 1])
            picks.append(filt.iloc[random_pick])
        elif filt.shape[0] == 1:
            picks.append(filt.iloc[0])

    
    while len(picks) < 5:
        pick_names = []
        for pick in picks:
            pick_names.append(pick['player'])
        bonus_segment = random.choice([segment_a, segment_b, segment_c, segment_d])
        filt = player_selection.loc[(player_selection['ranking'] >= bonus_segment[0]) & (player_selection['ranking'] <= bonus_segment[1]) & ~(player_selection['player'].isin(pick_names))]
        if filt.shape[0] > 0:
            picks.append(filt.iloc[0])
        if len(picks) == player_selection.loc[player_selection['ranking'] <= max_ranking].shape[0]:
            break

    # Put together a dataframe with only the user's favourites and the recommendations
    pick_names = []
    input_names = []
    for pick in picks:
        pick_names.append(pick['player'])
    for player in input_rows:
        input_names.append(player.iloc[0]['player'])
    master_names = pick_names + input_names

    players_input = players_alt_scaled.loc[players_alt_scaled['player'].isin(input_names)]
    players_picked = players_alt_scaled.loc[players_alt_scaled['player'].isin(pick_names)]
    players_picked = pd.merge(players_picked, pd.DataFrame(picks), on='player', how='left')[['player', 'tour_x', 'ranking_x', 'country_x', 'age_x', 'stat_offset', 'strong_stat_x', 'strong_diff', 'weak_stat_x', 'weak_diff']+features+['strong_surface_x', 'weak_surface_x']]

    players_picked = players_picked.rename({
        'tour_x': 'tour',
        'ranking_x': 'ranking',
        'country_x': 'country',
        'age_x': 'age',
        'grand_slam_x': 'grand_slam',
        'strong_stat_x': 'strong_stat',
        'weak_stat_x': 'weak_stat',
        'strong_surface_x': 'strong_surface',
        'weak_surface_x': 'weak_surface'
    }, axis=1)

    # Create a table that looks at the favourites and evaluates how significant the relationship between them in the stats is
    input_dist = players_input.describe().iloc[1:3][features].transpose().fillna(1)
    input_dist['scaled_mean'] = input_dist['mean'] - input_dist['mean'].mean()
    input_dist['value'] = input_dist['scaled_mean'] / input_dist['std']
    input_dist = input_dist.sort_values('value', ascending=False)[['value', 'scaled_mean']]

    model_role = """
    You are an assistant for recommending tennis players to watch based on a user's existing preferences. 
    Your tone is matter-of-fact but also welcoming and friendly. You should only refer to the provided data for your claims.
    """

    if country:
        model_prompt = f"""
        The user already likes the following players: {input_names}. Recommend them to watch the following players: {pick_names}, in the following format: 
        1. Name (Tour #Ranking, age Age): Justification, connecting the player to at least one of the user's favourite players. 
        The focus of the justification is on playstyle based on the provided data. 
        For {country_selection.iloc[0]}, you must mention their nationality e.g. "another [nationality] player", since they were picked based on one of the user's favourites. Put the nationality in bold. 
        Also, before listing the recommendations, write a short summary of the user's favourites and how they inform what kind of other players they might like to watch. 
        In this summary, you should point out the top 2-4 most significant stats that jump out based on the provided data. Mention at least 1 weakness. 
        Do not explicitly state any numbers besides ranking. 
        Address the user as 'you'. 
        Mention that some lower-ranked players are suggested for the sake of variety. 
        Put the names of statistics in bold so they jump out to the user, translated into natural language rather than the raw column name.
        """
    else:
        model_prompt = f"""
        The user already likes the following players: {input_names}. Recommend them to watch the following players: {pick_names}, in the following format: 
        1. Name (Tour #Ranking, age Age): Justification, connecting the player to at least one of the user's favourite players. 
        The focus of the justification is on playstyle based on the provided data. 
        Also, before listing the recommendations, write a short summary of the user's favourites and how they inform what kind of other players they might like to watch. 
        In this summary, you should point out the top 2-4 most significant stats that jump out based on the provided data. Mention at least 1 weakness. 
        Do not explicitly state any numbers besides ranking. 
        Address the user as 'you'. 
        Mention that some lower-ranked players are suggested for the sake of variety. 
        Put the names of statistics in bold so they jump out to the user, translated into natural language rather than the raw column name.
        """

    client = OpenAI(
      base_url="https://openrouter.ai/api/v1", # 
      api_key=OPENROUTER_API_KEY,              # 
    )

    pd.concat([players_input, players_picked]).to_csv('players_picked.csv')
    input_dist.to_csv('input_stats.csv')

    output_file = pd.concat([players_input, players_picked]).to_csv()
    input_file = input_dist.to_csv()

    # This file explains the column names
    with open("columns.txt") as f:
        column_info = f.read()

    f.close()

    llm_answer = client.chat.completions.create(
        model="google/gemini-2.5-flash",
        messages=[
            {'role': 'system', 'content': model_role},
            {'role': 'user', 'content': output_file},
            {'role': 'user', 'content': input_file},
            {'role': 'user', 'content': column_info},
            {'role': 'user', 'content': model_prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )

    return llm_answer.choices[0].message.content, pd.concat([players_input, players_picked])