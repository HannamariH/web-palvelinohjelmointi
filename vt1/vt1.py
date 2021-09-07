import simplejson as json
import urllib.request
from flask import Flask
app = Flask(__name__)

@app.route('/') #tämä rivi kertoo osoitteen, josta tämä sovellus löytyy
def load_data():
    result = ""

    with urllib.request.urlopen("http://hazor.eu.pythonanywhere.com/2021/data2021.json") as response:
        data = json.load(response)

        alpha_list = teams_alphabetical(data)

        """for x in data["items"]["item"]:
            result += x["name"]
            for topping in x["topping"]:
                try:
                    result +=  topping["type"]
                except KeyError:
                    pass
            try:
                filling = x["fillings"]["filling"]
                for x in filling:
                    result += x["name"]
            except KeyError:
                pass"""

        text = ""
        for x in alpha_list:
            text += x + "\n\n"

    return text

# TODO: virheenkäsittely, jos/kun sarja/joukkue/nimi puuttuu
def teams_alphabetical(data):

    team_list = []

    for x in data["sarjat"]:
        for y in x["joukkueet"]:
            team_list.append(y["nimi"])

    team_list.sort()
    return team_list


