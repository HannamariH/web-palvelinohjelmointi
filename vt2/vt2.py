from flask import Flask, Response, request, render_template
from flask_wtf.csrf import CSRFProtect
from polyglot import PolyglotForm
import json
import urllib.request
from wtforms import IntegerField, StringField, validators, IntegerField
app = Flask(__name__)

csrf = CSRFProtect(app)
app.secret_key = '"\xf9$T\x88\xefT8[\xf1\xc4Y-r@\t\xec!5d\xf9\xcc\xa2\xaa'

@app.route('/', methods=["GET", "POST"])
def chess():

    #haetaan asetukset ja otetaan ne talteen
    with urllib.request.urlopen("https://europe-west1-ties4080.cloudfunctions.net/vt2_taso1") as response:
        conf = json.load(response)

    first = conf["first"]
    balls_direction = conf["balls"]
    min = conf["min"]
    max = conf["max"]

    #luodaan lomake
    class ChessForm(PolyglotForm):
        x = IntegerField('Laudan koko', validators=[validators.InputRequired(message="Syöttämäsi arvo ei kelpaa"), validators.NumberRange(min=min,max=max, message="Syöttämäsi arvo ei kelpaa")])
        pelaaja1 = StringField('Pelaaja 1', validators=[validators.InputRequired(message="Syötä pelaajan nimi"), validators.Length(min=1, message="Syötä pelaajan nimi")])
        pelaaja2 = StringField("Pelaaja 2", validators=[validators.InputRequired(message="Syötä pelaajan nimi"), validators.Length(min=1, message="Syötä pelaajan nimi")])

    form = ChessForm()

    #poimitaan pelaajien nimet ja laudan koko lomakkeelta
    try:
        pelaaja1 = request.values.get("pelaaja1")
        if not pelaaja1:
            pelaaja1 = "Pelaaja 1"
    except:
        pelaaja1 = "Pelaaja 1"

    try:
        pelaaja2 = request.values.get("pelaaja2")
        if not pelaaja2:
            pelaaja2 = "Pelaaja 2"
    except:
        pelaaja2 = "Pelaaja 2"

    try:
        x = int(request.values.get("x"))
        if x < min or x > max:
            x = min
    except:
        x = min

    #validoidaan lomakekenttien syötteet
    if request.method == 'POST':
        form.validate()

    return Response(render_template("pohja.xhtml", form=form, pelaaja1=pelaaja1, pelaaja2=pelaaja2, x=x, first=first, balls_direction=balls_direction), mimetype="application/xhtml+xml;charset=UTF-8") 