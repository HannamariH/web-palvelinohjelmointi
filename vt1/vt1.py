import json
import urllib.request
from flask import Flask, Response, request
from random import randint
from datetime import timedelta
from math import sin, cos, sqrt, atan2, radians
app = Flask(__name__)


@app.route('/')
def load_data():

    reset = request.args.get("reset")
    if reset == "1":
        url = "http://hazor.eu.pythonanywhere.com/2022/data2022.json"
    else:
        url = "https://hahelle.eu.pythonanywhere.com/data.json"

    with urllib.request.urlopen(url) as response:
        global data
        data = json.load(response)

        # luodaan query parametrien perusteella lisättävä joukkue
        params = request.args
        state = params.get("tila")
        team_name = params.get("nimi")
        team_set = params.get("sarja")
        team_id = params.get("id")
        team_members = params.getlist("jasen")
        stamp_methods = get_stamp_indexes(params.getlist("leimaustapa"))

        if (state == "delete"):
            delete_team(team_set, team_name)

        elif (state == "insert"):

            newTeam = {
                "nimi": team_name,
                "jasenet": team_members,
                "id": "",
                "leimaukset": [],
                "leimaustapa": stamp_methods
            }

            # lisätään joukkue sarjaan
            for set in data["sarjat"]:
                if set["nimi"].upper() == team_set.upper():
                    newSet = add_team(set, newTeam)
                    # korvataan sarjalla aiempi sarja
                    set = newSet
        
        elif (state == "update"):
            newTeam = {
                "nimi": team_name,
                "jasenet": team_members,
                "leimaustapa": stamp_methods
            }
            data = update_team(newTeam, team_id, team_set)


        with open('data.json', 'w', encoding="utf-8") as outfile:
            json.dump(data, outfile)

        alpha_list = teams_alphabetical()
        integer_cps = starts_with_integer()
        results = print_results()
        text = ""
        for x in alpha_list:
            text = text + x + "\n"
        text = text + "\n" + integer_cps + "\n\n" + results

    return Response(text, mimetype="text/plain;charset=UTF-8")

# algoritmi:
# etsitään id:n perusteella oikea joukkue
# jos ollaan eri sarjassa kuin on annettu, tarkistetaan, onko annettua sarjaa olemassa
# jos ei ole, päivitetään joukkue muilta osin
# jos sarja on olemassa, siirretään päivitetty joukkue sinne

def update_team(u_team, id, team_set):
    break_flag = False
    for set in data["sarjat"]:   
        for team in set["joukkueet"]:
            # etsitään id:n perusteella oikea joukkue
            if int(team["id"]) == int(id):
                team["nimi"] = u_team["nimi"]
                team["jasenet"] = u_team["jasenet"]
                team["leimaustapa"] = u_team["leimaustapa"]
                if set["nimi"].upper() != team_set.upper():
                    #poista alkup. joukkue
                    set["joukkueet"].remove(team)
                    #siirry toiseen sarjaan, lisää muokattu joukkue sinne
                    for index, set in enumerate(data["sarjat"]):
                        if set["nimi"].upper() == team_set.upper():
                            data["sarjat"][index]["joukkueet"].append(team)
                break_flag = True
                break
        if break_flag:
            break
    return data


def get_stamp_indexes(stamps):
    stamping_methods = data["leimaustapa"]
    indexes = []
    for stamp in stamps:
        try:
            indexes.append(stamping_methods.index(stamp))
        except ValueError:
            continue
    return indexes


def teams_alphabetical():

    team_list = []

    for x in data["sarjat"]:
        for y in x["joukkueet"]:
            try:
                team_list.append(y["nimi"])
            except KeyError:
                pass

    # järjestää listan alkiot kirjainkoosta välittämättä
    team_list.sort(key=lambda x: x.lower())

    return team_list


def add_team(set, team):

    # tarkistaa, että datassa on ko. sarja
    setNames = []
    for s in data["sarjat"]:
        setNames.append(s["nimi"])
    if set["nimi"] not in setNames:
        # palauta set sellaisenaan
        return set

    # tarkistaa, että joukkueessa on oikeat avaimet
    keys = ["nimi", "jasenet", "id", "leimaustapa", "leimaukset"]
    for key in keys:
        if key not in team.keys():
            # palauta set sellaisenaan
            return set

    # tarkistaa, että joukkueen nimi on uniikki
    newTeamNameStripped = team["nimi"].strip().upper()
    for s in data["sarjat"]:
        for teams in s["joukkueet"]:
            candidateNameStripped = teams["nimi"].strip().upper()
            if candidateNameStripped == newTeamNameStripped:
                # palauta set sellaisenaan
                return set

    id = get_id()
    team["id"] = id

    # lisää joukkue
    set["joukkueet"].append(team)
    return set


def get_id():
    id = randint(1000000000000000, 9999999999999999)
    for set in data["sarjat"]:
        for team in set["joukkueet"]:
            if team["id"] == id:
                return get_id()
    return id


def starts_with_integer():
    cps = ""
    for cp in data["rastit"]:
        if cp["koodi"][0].isdigit():
            cps += cp["koodi"] + ";"
    cps = cps[:-1]
    return cps


def delete_team(set_name, team_name):
    # etsitään oikea sarja
    for s in range(len(data["sarjat"])):
        if data["sarjat"][s]["nimi"].strip().upper() == set_name.strip().upper():
            setti = data["sarjat"][s]
            # etsitään oikea joukkue
            for t in range(len(setti["joukkueet"])):
                if setti["joukkueet"][t]["nimi"].strip().upper() == team_name.strip().upper():
                    del data["sarjat"][s]["joukkueet"][t]
                    break

# TODO: saako olettaa, että päivä on kaikilla sama?
def get_team_time(stamps):
    start_time = stamps[0]["aika"].split()[1]
    splitted = start_time.split(":")
    start_delta = timedelta(hours=int(splitted[0]), minutes=int(
        splitted[1]), seconds=int(splitted[2]))
    finish_time = stamps[-1]["aika"].split()[1]
    splitted = finish_time.split(":")
    finish_delta = timedelta(hours=int(splitted[0]), minutes=int(
        splitted[1]), seconds=int(splitted[2]))

    time_used = finish_delta - start_delta
    time_used_string = str(time_used)
    # jos tunnit on ilmoitettu yhdellä numerolla, lisätään nolla eteen
    if len(time_used_string.strip(":")[0]) < 2:
        time_used_string = (f"0{time_used_string}")

    return time_used_string


def get_team_distance(stamps, cps):

    # kerätään rastien lat & lon listaan
    points = []
    for stamp in stamps:
        cp = str(stamp["rasti"])
        for controlpoint in cps:
            id = str(controlpoint["id"])
            if id == cp:
                try:
                    lat = float(controlpoint["lat"])
                    lon = float(controlpoint["lon"])
                    points.append((lat, lon))
                except (ValueError, TypeError):
                    pass

    # maapallon säde kilomerteinä (noin)
    R = 6373.0

    # käydään points läpi, lasketaan jokaisen rastivälin mitta ja lasketaan yhteen
    full_distance = 0
    starting_point = points[0]
    lat1 = radians(starting_point[0])
    lon1 = radians(starting_point[1])
    for tuple in points:
        lat2 = radians(tuple[0])
        lon2 = radians(tuple[1])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c
        full_distance += distance
        lat1 = lat2
        lon1 = lon2

    return (f"{round(full_distance)} km")


def print_results():
    cps = data["rastit"]
    sets = data["sarjat"]
    teams_data = []
    teams_listed = ""

    for set in sets:
        for team in set["joukkueet"]:
            team_data = []
            points = 0
            # sorttaa leimaukset aikajärjestykseen
            newStamps = sorted(team["leimaukset"], key=lambda cp: str(cp["aika"]))
            # TODO: tämä olettaa, että lahto on oletuksena eka! entä jos lähtöä ei ole ollenkaan??
            lahto_index = 0
            # poistetaan LAHTOa edeltävät
            for i in range(len(newStamps)):
                cp = newStamps[i]["rasti"]
                for controlpoint in cps:
                    id = str(controlpoint["id"])
                    if id == str(cp):
                        if str(controlpoint["koodi"]).upper() == "LAHTO":
                            lahto_index = i
                    # TODO: jos lähtörastia ei löydy ollenkaan, siirry seuraavaan joukkueeseen
            # poistetaan lahto_indexiä aiemmat dictit newStampsista
            if lahto_index > 0:
                newStamps = newStamps[lahto_index:]
            # poistetaan MAALIn jälkeiset
            maali_index = -1
            # käydään läpi joukkueen leimaukset
            for i in range(len(newStamps)):
                cp = newStamps[i]["rasti"]
                # käydään läpi rastien koodit
                for controlpoint in cps:
                    id = str(controlpoint["id"])
                    if id == str(cp):
                        if str(controlpoint["koodi"]).upper() == "MAALI":
                            maali_index = i
                            # pysähdytään ekaan MAALI-leimaukseen
                            break
                else:
                    continue
                break
            if maali_index < len(newStamps)-1:
                # poistetaan maali_indexin jälkeiset dictit newStampsista
                newStamps = newStamps[:maali_index+1]

            # poistetaan tuplakäynnit samalla rastilla
            cp_codes = []
            # looppaus takaperin, jotta indeksit säilyy
            for i in range(len(newStamps)-1, -1, -1):
                cp = str(newStamps[i]["rasti"])
                if cp in cp_codes:
                    newStamps.pop(i)
                else:
                    cp_codes.append(cp)

            # pisteiden lasku
            for stamp in newStamps:
                cp = stamp["rasti"]
                for controlpoint in cps:
                    id = str(controlpoint["id"])
                    if id == str(cp):
                        code = str(controlpoint["koodi"])
                        firstChar = code[0]
                        if firstChar.isdigit():
                            points = points + int(firstChar)
            team_points = (team["nimi"], points)
            members_sorted = sorted(team["jasenet"])
            team_data.append(team_points)
            team_data.append(members_sorted)
            if newStamps:
                team_distance = get_team_distance(newStamps, data["rastit"])
                team_data.append(team_distance)
                team_time = get_team_time(newStamps)
                team_data.append(team_time)
            else:
                team_data = team_data + ["0 km", "00:00:00"]
            teams_data.append(team_data)

    # kaksiportainen sorttaus: ensin toissijaiset 
    # (käytetyn ajan ja joukkueen nimen mukaan järjestykseen)
    sorted_teams_once = sorted(teams_data, key=lambda x: (x[3], x[0][0].upper()))
    # sitten ensisijainen sorttaus (pisteiden mukaan laskevaan järjestykseen)
    sorted_teams_twice = sorted(sorted_teams_once, key=lambda x: x[0][1], reverse=True)
    # luodaan tulostus joukkueiden pisteistä
    for team in sorted_teams_twice:
        teams_listed += f"{team[0][0]} ({team[0][1]} p, {team[2]}, {team[3]})\n"
        for member in team[1]:
            teams_listed += f"  {member}\n"
    return teams_listed
