import json
import urllib.request
import urllib.parse
from flask import Flask, Response, request
from random import randint
app = Flask(__name__)

@app.route('/')
def load_data():

    with urllib.request.urlopen("http://hazor.eu.pythonanywhere.com/2022/data2022.json") as response:
        global data
        data = json.load(response)

        #luodaan query parametrien perusteella lisättävä joukkue
        params = request.args
        team_name = params.get("nimi")
        if (team_name):
            team_name = urllib.parse.unquote(team_name)
        team_members = params.getlist("jasen")
        if (team_members):
            for member in team_members:
                member = urllib.parse.unquote(member)
        team_set = params.get("sarja")
        state = params.get("tila")

        if (state == "delete"):
            deleteTeam(team_set, team_name)

        if (state == "insert"):
            newTeam = {
                "nimi": team_name,
                "jasenet": team_members,
                "id": "",
                "leimaukset": [],
                "leimaustapa": []
            }

            #lisätään joukkue sarjaan
            for set in data["sarjat"]:
                if set["nimi"].upper() == team_set.upper():
                    newSet = add_team(set, newTeam)
                    #korvataan sarjalla aiempi sarja
                    set = newSet

        with open('data.json', 'w', encoding="utf-8") as outfile:
            json.dump(data, outfile)

        alpha_list = teams_alphabetical()
        integer_cps = starts_with_integer()
        text = ""
        for x in alpha_list:
            text = text + x + "\n"
        text = text + "\n" + integer_cps        

    return Response(text, mimetype="text/plain;charset=UTF-8")


def teams_alphabetical():

    team_list = []

    for x in data["sarjat"]:
        for y in x["joukkueet"]:
            try:
                team_list.append(y["nimi"])
            except KeyError:
                pass

    #järjestää listan alkiot kirjainkoosta välittämättä
    team_list.sort(key = lambda x: x.lower())

    return team_list


def add_team(set, team):

    #tarkistaa, että datassa on ko. sarja
    setNames = []
    for s in data["sarjat"]:
        setNames.append(s["nimi"])
    if set["nimi"] not in setNames:
        #palauta set sellaisenaan
        return set

    #tarkistaa, että joukkueessa on oikeat avaimet
    keys = ["nimi", "jasenet", "id", "leimaustapa", "leimaukset"]
    for key in keys:
        if key not in team.keys():
            #palauta set sellaisenaan
            return set

    #tarkistaa, että joukkueen nimi on uniikki
    newTeamNameStripped = team["nimi"].strip().upper()
    for s in data["sarjat"]:    
        for teams in s["joukkueet"]:       
            candidateNameStripped = teams["nimi"].strip().upper()
            if candidateNameStripped == newTeamNameStripped:        
                #palauta set sellaisenaan    
                return set
    
    id = getId()
    team["id"] = id

    #lisää joukkue
    set["joukkueet"].append(team)
    return set

def getId():
    id = randint(1000000000000000, 9999999999999999)
    for set in data["sarjat"]:    
        for team in set["joukkueet"]:
            if team["id"] == id:
                return getId()
    return id

def starts_with_integer():
        cps = ""
        for cp in data["rastit"]:    
            if cp["koodi"][0].isdigit():
                cps+=cp["koodi"] + ";"
        cps = cps[:-1]
        return cps

def deleteTeam(set_name, team_name):
    #etsitään oikea sarja
    for s in range(len(data["sarjat"])):
        if data["sarjat"][s]["nimi"].strip().upper() == set_name.strip().upper():
            setti = data["sarjat"][s]
            #etsitään oikea joukkue
            for t in range(len(setti)):
                if setti["joukkueet"][t]["nimi"].strip().upper() == team_name.strip().upper():
                    del data["sarjat"][s]["joukkueet"][t]["nimi"]
                    break
