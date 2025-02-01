import random
import requests
import json
from datetime import timezone
import datetime
import copy
import pandas as pd
import dataframe_image as dfi
import matplotlib
from zoneinfo import ZoneInfo
import pytz
import threading
import concurrent.futures


# Today's Games: "https://api-web.nhle.com/v1/schedule/2025-01-18"
# Game Boxscore: https://api-web.nhle.com/v1/gamecenter/GAME_ID/boxscore

endOfSeason = datetime.date(2025, 4, 18)
# endOfSeason = datetime.date(2025, 2, 5)
simulations = 100000
# simulations = 1000

winPctDict = {}
games = {}
outcome = {}
schedule = {}
oddsMatrix = {}
firstRound = {}
tempPct = {}
todayGameCount = 0
finalPos = [0, 0, 0, 0, 0, 0]
schedFlag = False

# Set one of these four values to be true.
ptPct = False
coinFlip = True
goalDiffOdds = False
log5 = False
goalDiffOddsCalc = 'base'  # Either 'log5' or 'base', only used if goalDiffOdds = True

homeAdvantage = 0.0342  # Home teams win 53.42% of games in the 2024-25 season.
avgPtPct = 0.55  # The average NHL team has a win% of .550

pctMoving = False  # Have Pt% update every simulated game
teamFocus = "OTT"


def gameSimulator(team1name, team1pct, team2name, team2pct, homeGoalsFor, homeGoalsAgainst, homeGamesPlayed, awayGoalsFor, awayGoalsAgainst, awayGamesPlayed):
    if ptPct:
        team1odd = team1pct / (team1pct + team2pct) + homeAdvantage
    elif coinFlip:
        team1odd = 0.5 + homeAdvantage
    elif goalDiffOdds:
        team1E = ((homeGoalsFor / homeGamesPlayed) + (homeGoalsAgainst / homeGamesPlayed)) ** avgPtPct
        team1calc = (homeGoalsFor ** team1E)/((homeGoalsFor ** team1E) + (homeGoalsAgainst ** team1E))

        team2E = ((awayGoalsFor / awayGamesPlayed) + (awayGoalsAgainst / awayGamesPlayed)) ** avgPtPct
        team2calc = (awayGoalsFor ** team2E)/((awayGoalsFor ** team2E) + (awayGoalsAgainst ** team2E))

        if goalDiffOddsCalc == 'log5':
            team1odd = (team1calc - team1calc * team2calc) / (team1calc + team2calc - 2 * team1calc * team2calc) + homeAdvantage
        else:
            team1odd = team1calc / (team1calc + team2calc) + homeAdvantage

    elif log5:
        team1odd = (team1pct - team1pct * team2pct) / (team1pct + team2pct - 2 * team1pct * team2pct) + homeAdvantage

    # Generate a random number from 0-1
    value = random.random()

    # If the value is less than team 1's odds of winning, team 1 wins. Otherwise, team 2 wins.
    if value < team1odd:
        winner = team1name
    else:
        winner = team2name

    # Approx. 23% of games go to OT, and 8% go to shootout. Check if the value is in the top/bottom 11.5%, and the top/bottom 4%.
    if value < 0.115 or value > 0.885:
        if value < 0.04 or value > 0.96:
            decision = "SO"
        else:
            decision = "OT"
    else:
        decision = "REG"

    return winner, decision


def getTodaysGames(dateYear, dateMonth, dateDay):
    global todayGameCount
    print(f"Pulling today's games and the standings on {dateYear}-{dateMonth}-{dateDay}")
    url = f"https://api-web.nhle.com/v1/schedule/{dateYear}-{dateMonth}-{dateDay}"
    standingsUrl = f"https://api-web.nhle.com/v1/standings/{dateYear}-{dateMonth}-{dateDay}"

    resp = requests.get(standingsUrl)
    standings = resp.json()

    # Extract info from the standings
    for i in standings['standings']:
        winPctDict[i['teamAbbrev']['default']] = {
            'winPct': i['pointPctg'],
            'wins': int(i['regulationPlusOtWins']),
            'losses': int(i['losses']),
            'otl': int(i['otLosses']),
            'gamesPlayed': int(i['gamesPlayed']),
            'conference': i['conferenceAbbrev'],
            'division': i['divisionAbbrev'],
            'homeGoalsFor': i['homeGoalsFor'],
            'homeGoalsAgainst': i['homeGoalsAgainst'],
            'homeGamesPlayed': i['homeGamesPlayed'],
            'awayGoalsFor': i['roadGoalsFor'],
            'awayGoalsAgainst': i['roadGoalsAgainst'],
            'awayGamesPlayed': i['roadGamesPlayed'],
            'pos1FirstRound': 0,
            'pos2FirstRound': 0,
            'pos3FirstRound': 0,
            'pos4FirstRound': 0,
            'pos5FirstRound': 0,
            'firstRoundTotal': 0,
        }

    resp = requests.get(url)
    weekGames = resp.json()

    todaysGames = weekGames['gameWeek'][0]['games']
    gameCount = 0

    # Extract info from today's games, only include games that have a team from the Eastern conference
    for i in todaysGames:
        if winPctDict[i['homeTeam']['abbrev']]['conference'] == winPctDict[teamFocus]['conference'] or winPctDict[i['awayTeam']['abbrev']]['conference'] == winPctDict[teamFocus]['conference']:
            games[gameCount] = {
                'home': i['homeTeam']['abbrev'],
                'away': i['awayTeam']['abbrev'],

                'homeWins': winPctDict[i['homeTeam']['abbrev']]['wins'],
                'homeLosses': winPctDict[i['homeTeam']['abbrev']]['losses'],
                'homeOTLosses': winPctDict[i['homeTeam']['abbrev']]['otl'],
                'homeGP': winPctDict[i['homeTeam']['abbrev']]['gamesPlayed'],
                'homeGoalsFor': winPctDict[i['homeTeam']['abbrev']]['homeGoalsFor'],
                'homeGoalsAgainst': winPctDict[i['homeTeam']['abbrev']]['homeGoalsAgainst'],
                'gamesPlayedHome': winPctDict[i['homeTeam']['abbrev']]['homeGamesPlayed'],

                'awayWins': winPctDict[i['awayTeam']['abbrev']]['wins'],
                'awayLosses': winPctDict[i['awayTeam']['abbrev']]['losses'],
                'awayOTLosses': winPctDict[i['awayTeam']['abbrev']]['otl'],
                'awayGP': winPctDict[i['awayTeam']['abbrev']]['gamesPlayed'],
                'awayGoalsFor': winPctDict[i['awayTeam']['abbrev']]['awayGoalsFor'],
                'awayGoalsAgainst': winPctDict[i['awayTeam']['abbrev']]['awayGoalsAgainst'],
                'gamesPlayedAway': winPctDict[i['awayTeam']['abbrev']]['awayGamesPlayed'],

                'gameTime': datetime.datetime.strptime(i['startTimeUTC'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(pytz.timezone("America/New_York")),
            }
            gameCount += 1
    todayGameCount = gameCount


def pullRemainingSchedule(pctDict):
    global schedule
    global schedFlag
    standings = copy.deepcopy(pctDict)
    if not schedFlag:
        currentDate = datetime.date.today()
        gameCounter = 0
        print("Requesting remaining schedule from NHL.")
        while currentDate < endOfSeason:
            url = f"https://api-web.nhle.com/v1/schedule/{currentDate.year}-{'{:02d}'.format(currentDate.month)}-{'{:02d}'.format(currentDate.day)}"
            resp = requests.get(url)
            jsonresp = resp.json()

            for game in jsonresp['gameWeek'][0]['games']:
                # Exclude 4 Nations Games
                if game['homeTeam']['abbrev'] != 'SWE' and game['homeTeam']['abbrev'] != 'FIN' and game['homeTeam']['abbrev'] != 'CAN' and game['homeTeam']['abbrev'] != 'USA' and game['homeTeam']['abbrev'] != 'TBD':
                    schedule[gameCounter] = {
                        'home': game['homeTeam']['abbrev'],
                        'homePct': standings[game['homeTeam']['abbrev']]['winPct'],
                        'homeGoalsFor': standings[game['homeTeam']['abbrev']]['homeGoalsFor'],
                        'homeGoalsAgainst': standings[game['homeTeam']['abbrev']]['homeGoalsAgainst'],
                        'homeGamesPlayed': standings[game['homeTeam']['abbrev']]['homeGamesPlayed'],
                        'away': game['awayTeam']['abbrev'],
                        'awayPct': standings[game['awayTeam']['abbrev']]['winPct'],
                        'awayGoalsFor': standings[game['awayTeam']['abbrev']]['awayGoalsFor'],
                        'awayGoalsAgainst': standings[game['awayTeam']['abbrev']]['awayGoalsAgainst'],
                        'awayGamesPlayed': standings[game['awayTeam']['abbrev']]['awayGamesPlayed'],
                    }
                    gameCounter += 1
            currentDate = currentDate + datetime.timedelta(days=1)
        schedFlag = True

    return schedule


def simSeason(pctDict, teamFocus):
    global schedule
    standings = copy.deepcopy(pctDict)
    schedule = pullRemainingSchedule(pctDict)

    # Simulate every remaining game in the NHL Schedule
    for game in schedule:
        # Simulate game
        winner, decision = gameSimulator(schedule[game]['home'], schedule[game]['homePct'], schedule[game]['away'], schedule[game]['awayPct'], schedule[game]['homeGoalsFor'], schedule[game]['homeGoalsAgainst'], schedule[game]['homeGamesPlayed'], schedule[game]['awayGoalsFor'], schedule[game]['awayGoalsAgainst'], schedule[game]['awayGamesPlayed'])

        # Logic to identify the stats coming out of the game
        if winner == schedule[game]['home']:
            standings[schedule[game]['home']]['wins'] += 1
            if decision != "REG":
                standings[schedule[game]['away']]['otl'] += 1
            else:
                standings[schedule[game]['away']]['losses'] += 1
        else:
            standings[schedule[game]['away']]['wins'] += 1
            if decision != "REG":
                standings[schedule[game]['home']]['otl'] += 1
            else:
                standings[schedule[game]['home']]['losses'] += 1

        standings[schedule[game]['home']]['gamesPlayed'] += 1
        standings[schedule[game]['away']]['gamesPlayed'] += 1

        # If 'reasess pt%' every game is enabled, reassess the pt%
        if pctMoving:
            standings[schedule[game]['home']]['winPct'] = (standings[schedule[game]['home']]['wins'] + (0.5 * standings[schedule[game]['home']]['otl'])) / standings[schedule[game]['home']]['gamesPlayed']
            standings[schedule[game]['away']]['winPct'] = (standings[schedule[game]['away']]['wins'] + (0.5 * standings[schedule[game]['away']]['otl'])) / standings[schedule[game]['away']]['gamesPlayed']

    # If 'reasess pt%' every game is not enabled, reassess the pt% at the end of the season to build the end-of-season standings
    if not pctMoving:
        for i in standings:
            standings[i]['winPct'] = (standings[i]['wins'] + (0.5 * standings[i]['otl'])) / standings[i]['gamesPlayed']

    # Run the playoff processor
    makePlayoffs, placement, competitor = playoffProcessor(standings, teamFocus)
    return makePlayoffs, placement, competitor


def playoffProcessor(standings, teamFocus):
    playoffsFlag = False
    competitor = "None"
    placement = 0
    atlPos = 1
    metPos = 1
    cenPos = 1
    pacPos = 1
    ewcPos = 4
    wwcPos = 4
    atlantic = {}
    metro = {}
    central = {}
    pacific = {}
    east = {}
    west = {}

    # Separate the teams into their divisions and conferences
    for team in standings:
        if standings[team]['conference'] == 'E':
            east[team] = standings[team]
            if standings[team]['division'] == 'A':
                atlantic[team] = standings[team]
            else:
                metro[team] = standings[team]
        else:
            west[team] = standings[team]
            if standings[team]['division'] == "C":
                central[team] = standings[team]
            else:
                pacific[team] = standings[team]

    # Sort the divisional standings, and only keep the top three by pt%
    atlantic = dict(sorted(atlantic.items(), key=lambda item: item[1]['winPct'], reverse=True)[:3])
    metro = dict(sorted(metro.items(), key=lambda item: item[1]['winPct'], reverse=True)[:3])
    central = dict(sorted(central.items(), key=lambda item: item[1]['winPct'], reverse=True)[:3])
    pacific = dict(sorted(pacific.items(), key=lambda item: item[1]['winPct'], reverse=True)[:3])

    # Remove the top three in the divisions from the conference groups
    east = {key: value for key, value in east.items() if key not in atlantic}
    east = {key: value for key, value in east.items() if key not in metro}
    west = {key: value for key, value in west.items() if key not in central}
    west = {key: value for key, value in west.items() if key not in pacific}

    # Sort the remaining teams in each conference, then keep the top two
    east = dict(sorted(east.items(), key=lambda item: item[1]['winPct'], reverse=True)[:2])
    west = dict(sorted(west.items(), key=lambda item: item[1]['winPct'], reverse=True)[:2])

    # Run through the divisions to identify playoff matchups
    for i in atlantic:
        if i == teamFocus:
            placement = atlPos
            playoffsFlag = True
            if atlPos == 1:
                # If the atlantic team in first place has more points than the metro team in first place,
                # ATL 1 plays WC2, otherwise ATL 1 plays WC1
                if next(iter(atlantic.values()))['winPct'] > next(iter(metro.values()))['winPct']:
                    competitor = list(east.keys())[1]
                else:
                    competitor = list(east.keys())[0]
            elif atlPos == 2:
                competitor = list(atlantic.keys())[2]
            elif atlPos == 3:
                competitor = list(atlantic.keys())[1]
        atlPos += 1
    for i in metro:
        if i == teamFocus:
            placement = metPos
            playoffsFlag = True
            if metPos == 1:
                if next(iter(atlantic.values()))['winPct'] < next(iter(metro.values()))['winPct']:
                    competitor = list(east.keys())[1]
                else:
                    competitor = list(east.keys())[0]
            elif metPos == 2:
                competitor = list(metro.keys())[2]
            elif metPos == 3:
                competitor = list(metro.keys())[1]
        metPos += 1
    for i in central:
        if i == teamFocus:
            placement = cenPos
            playoffsFlag = True
            if cenPos == 1:
                if next(iter(central.values()))['winPct'] > next(iter(pacific.values()))['winPct']:
                    competitor = list(west.keys())[1]
                else:
                    competitor = list(west.keys())[0]
            elif cenPos == 2:
                competitor = list(central.keys())[2]
            elif cenPos == 3:
                competitor = list(central.keys())[1]
        cenPos += 1
    for i in pacific:
        if i == teamFocus:
            placement = pacPos
            playoffsFlag = True
            if pacPos == 1:
                if next(iter(central.values()))['winPct'] < next(iter(pacific.values()))['winPct']:
                    competitor = list(west.keys())[1]
                else:
                    competitor = list(west.keys())[0]
            elif pacPos == 2:
                competitor = list(pacific.keys())[2]
            elif pacPos == 3:
                competitor = list(pacific.keys())[1]
        pacPos += 1
    for i in east:
        if i == teamFocus:
            placement = ewcPos
            playoffsFlag = True
            if ewcPos == 4:
                if next(iter(atlantic.values()))['winPct'] > next(iter(metro.values()))['winPct']:
                    competitor = list(metro.keys())[0]
                else:
                    competitor = list(atlantic.keys())[0]
            elif ewcPos == 5:
                if next(iter(atlantic.values()))['winPct'] < next(iter(metro.values()))['winPct']:
                    competitor = list(metro.keys())[0]
                else:
                    competitor = list(atlantic.keys())[0]
        ewcPos += 1
    for i in west:
        if i == teamFocus:
            placement = wwcPos
            playoffsFlag = True
            if wwcPos == 4:
                if next(iter(central.values()))['winPct'] > next(iter(pacific.values()))['winPct']:
                    competitor = pacific[0]
                else:
                    competitor = central[0]
            elif wwcPos == 5:
                if next(iter(central.values()))['winPct'] < next(iter(pacific.values()))['winPct']:
                    competitor = pacific[0]
                else:
                    competitor = central[0]
        wwcPos += 1
    return playoffsFlag, placement, competitor


def imageMaker(oddsMatrix, currentOdds, currentMatrix, standings, playoffCount):
    east = {}
    west = {}


    for team in standings:
        if standings[team]['conference'] == 'E':
            east[team] = standings[team]
        else:
            west[team] = standings[team]

    # Only set up for the eastern conference, used for Playoff Opponent Predictor
    east = dict(sorted(east.items(), key=lambda item: item[1]['firstRoundTotal'], reverse=True))
    # west = dict(sorted(west.items(), key=lambda item: item[1]['firstRoundTotal'], reverse=True))
    east = {team: data for team, data in east.items() if data.get("firstRoundTotal", 0) != 0}

    # Making the dataframe for today's games impact on the odds
    df = pd.DataFrame()
    dfNum = pd.DataFrame()
    for i in oddsMatrix:
        df[oddsMatrix[i]['game']] = [oddsMatrix[i]['awayWin']['oddsDiff'], oddsMatrix[i]['awayOT']['oddsDiff'], oddsMatrix[i]['homeOT']['oddsDiff'], oddsMatrix[i]['homeWin']['oddsDiff']]
        dfNum[f"{oddsMatrix[i]['game']}\n{oddsMatrix[i]['gameTime']}"] = [oddsMatrix[i]['awayWin']['oddsDiffNum'], oddsMatrix[i]['awayOT']['oddsDiffNum'], oddsMatrix[i]['homeOT']['oddsDiffNum'], oddsMatrix[i]['homeWin']['oddsDiffNum']]
    df.index = ['Away Win', 'Away OTW', 'Home OTW', 'Home Win']
    dfNum.index = ['Away Win', 'Away OTW', 'Home OTW', 'Home Win']

    # Highlight top and bottom odds for each game
    styled_dfNum = dfNum.style.highlight_max(color= 'green', axis = 0, props='background-color: #BEEAE5; color: black')
    styled_dfNum = styled_dfNum.highlight_min(color = 'red', axis = 0, props='background-color: #FFCFC9; color: black')
    styled_dfNum.set_caption(f"Senators current playoff odds: {currentOdds:.2%}")

    # Make em look pretty
    styled_dfNum = styled_dfNum.format(
        lambda x:f'+{x:.2f}%' if x > 0 else f'{x:.2f}%', precision = 2
    )

    dfi.export(styled_dfNum, 'Odds.png', table_conversion='matplotlib')

    # Make the Playoff Position dataframe
    df2 = pd.DataFrame()
    df2["Finish %"] = [f"{currentMatrix[1]/simulations:.2%}", f"{currentMatrix[2]/simulations:.2%}", f"{currentMatrix[3]/simulations:.2%}", f"{currentMatrix[4]/simulations:.2%}", f"{currentMatrix[5]/simulations:.2%}", f"{currentMatrix[0]/simulations:.2%}"]

    df2.index = ['Atlantic - 1', 'Atlantic - 2', 'Atlantic - 3', 'Wild Card 1', 'Wild Card 2', 'Miss Playoffs']
    print(df2)
    dfi.export(df2, 'Positioning.png', table_conversion='matplotlib')

    rows = []

    # Fix the 'dividebyzero' error in the worst way possible
    if currentMatrix[1] == 0:
        currentMatrix[1] = 1
    if currentMatrix[2] == 0:
        currentMatrix[2] = 1
    if currentMatrix[3] == 0:
        currentMatrix[3] = 1
    if currentMatrix[4] == 0:
        currentMatrix[4] = 1
    if currentMatrix[5] == 0:
        currentMatrix[5] = 1

    # Print the rows into the dataframe one by one
    for i in east:
        rows.append([i, standings[i]['pos1FirstRound']/currentMatrix[1]*100, standings[i]['pos2FirstRound']/currentMatrix[2]*100, standings[i]['pos3FirstRound']/currentMatrix[3]*100, standings[i]['pos4FirstRound']/currentMatrix[4]*100, standings[i]['pos5FirstRound']/currentMatrix[5]*100, standings[i]['firstRoundTotal']/playoffCount*100])

    # Add the column headers
    df3 = pd.DataFrame(rows, columns=["Team", "Atlantic - 1", "Atlantic - 2", "Atlantic - 3", "Wild Card 1", "Wild Card 2", "Total %"])

    # Make it look pretty
    df3.set_index('Team', inplace=True)
    df3.columns = [col[:12] for col in df3.columns]
    df3 = df3.style.highlight_max(color='green', axis=0, props='background-color: #BEEAE5; color: black')
    df3 = df3.format('{:.2f}%', subset=["Atlantic - 1", "Atlantic - 2", "Atlantic - 3", "Wild Card 1", "Wild Card 2", "Total %"])
    df3.set_caption("Prospective First Round Opponents")
    dfi.export(df3, "First Round Opponents.png", table_conversion='matplotlib')


def optionProcess(homeWins, homeOTL, homeLosses, awayWins, awayOTL, awayLosses, game, winPctDict, gameType):
    # Function to process the possible outcomes of today's games
    playoffCount = 0
    tempFinalPos = copy.deepcopy(finalPos)

    # Add the necessary values to the dict
    for i in range(0, simulations):
        tempPct = copy.deepcopy(winPctDict)
        tempPct[games[game]['home']]['wins'] += homeWins
        tempPct[games[game]['home']]['otl'] += homeOTL
        tempPct[games[game]['home']]['losses'] += homeLosses
        tempPct[games[game]['away']]['wins'] += awayWins
        tempPct[games[game]['away']]['otl'] += awayOTL
        tempPct[games[game]['away']]['losses'] += awayLosses
        tempPct[games[game]['home']]['gamesPlayed'] += 1
        tempPct[games[game]['away']]['gamesPlayed'] += 1

        tempPct[games[game]['home']]['winPct'] = (games[game]['homeWins'] + (0.5 * games[game]['homeOTLosses'])) / (
        games[game]['homeGP'])
        tempPct[games[game]['away']]['winPct'] = (games[game]['awayWins'] + (0.5 * games[game]['awayOTLosses'])) / (
        games[game]['awayGP'])
        playoffs, placement, competitor = simSeason(tempPct, teamFocus)
        tempFinalPos[placement] += 1
        if playoffs:
            playoffCount += 1

    print(f"{games[game]['home']} v. {games[game]['away']} - {gameType}: {playoffCount / simulations:.2%}")

    # Make it look pretty despite the fact that oddsDiff doesn't get used anymore
    if (playoffCount / simulations) - currentOdds > 0:
        oddsDiff = f"+{(playoffCount / simulations) - currentOdds:.2%}"
    else:
        oddsDiff = f"{(playoffCount / simulations) - currentOdds:.2%}"

    oddsMatrix[game][gameType] = {
        'pos': tempFinalPos,
        'odds': f"{playoffCount / simulations:.2%}",
        'oddsDiff': oddsDiff,
        'oddsDiffNum': ((playoffCount / simulations) - currentOdds) * 100,
    }

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    startTime = datetime.datetime.now()
    currentDate = datetime.date.today()
    print("Pulling today's games")
    getTodaysGames(currentDate.year, '{:02d}'.format(currentDate.month), '{:02d}'.format(currentDate.day))

    currentPlayoffCount = 0
    tempFinalPos = copy.deepcopy(finalPos)
    print("Identifying current odds")
    for i in range(0, simulations):
        tempPct = copy.deepcopy(winPctDict)
        playoffs, placement, competitor = simSeason(tempPct, teamFocus)
        if competitor != "None":
            winPctDict[competitor]['firstRoundTotal'] += 1
        if placement == 1:
            winPctDict[competitor]['pos1FirstRound'] += 1
        elif placement == 2:
            winPctDict[competitor]['pos2FirstRound'] += 1
        elif placement == 3:
            winPctDict[competitor]['pos3FirstRound'] += 1
        elif placement == 4:
            winPctDict[competitor]['pos4FirstRound'] += 1
        elif placement == 5:
            winPctDict[competitor]['pos5FirstRound'] += 1

        tempFinalPos[placement] += 1
        if playoffs:
            currentPlayoffCount += 1
    # Current Odds
    print("Current Odds")
    print(tempFinalPos)
    currentOdds = currentPlayoffCount / simulations
    currentMatrix = tempFinalPos
    print(f"{currentPlayoffCount / simulations:.2%}")

    gameCount = 1
    for game in games:
        print(f"Processing game {gameCount}/{todayGameCount}: {games[game]['home']} v. {games[game]['away']}")
        oddsMatrix[game] = {
            'game': f"{games[game]['away']} @ {games[game]['home']}",
            'gameTime': games[game]['gameTime'].strftime("%I:%M %p"),
            'homeWin': {},
            'homeOT': {},
            'awayOT': {},
            'awayWin': {},
        }
        argsList = [
            (1, 0, 0, 0, 0, 1, game, winPctDict, "homeWin"),
            (1, 0, 0, 0, 1, 0, game, winPctDict, "homeOT"),
            (0, 0, 1, 1, 0, 1, game, winPctDict, "awayOT"),
            (0, 0, 1, 1, 0, 0, game, winPctDict, "awayWin")
        ]

        # Despite my most mediocre attempts to get threading to work, I did not.
        # This doesn't run any faster than just running them one at a time.
        # This is the version that worked the least poorly
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(optionProcess, *args): args for args in argsList}

            for future in concurrent.futures.as_completed(futures):
                future.result()

        ## Threading attempt one.
        # t1 = threading.Thread(target=optionProcess, args=(1, 0, 0, 0, 0, 1, winPctDict, "homeWin"))  # Home Win
        # t2 = threading.Thread(target=optionProcess, args=(1, 0, 0, 0, 1, 0, winPctDict, 'homeOT'))  # Home OTW
        # t3 = threading.Thread(target=optionProcess, args=(0, 0, 1, 1, 0, 1, winPctDict, 'awayOT'))  # Away OTW
        # t4 = threading.Thread(target=optionProcess, args=(0, 0, 1, 1, 0, 0, winPctDict, "awayWin"))  # Away Win
        #
        # t1.start()
        # t2.start()
        # t3.start()
        # t4.start()
        #
        # t1.join()
        # t2.join()
        # t3.join()
        # t4.join()

        ## Running one at a time
        # optionProcess(1, 0, 0, 0, 0, 1, winPctDict, "homeWin")  # Home Win
        # optionProcess(1, 0, 0, 0, 1, 0, winPctDict, 'homeOT')  # Home OTW
        # optionProcess(0, 0, 1, 1, 0, 1, winPctDict, 'awayOT')  # Away OTW
        # optionProcess(0, 0, 1, 1, 0, 0, winPctDict, "awayWin")  # Away Win

        gameCount += 1
    imageMaker(oddsMatrix, currentOdds, currentMatrix, winPctDict, currentPlayoffCount)

    completionTime = datetime.datetime.now()
    duration = completionTime - startTime
    print(f"Duration to process: {duration}")
