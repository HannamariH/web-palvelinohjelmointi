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

    try:
        clicked = request.values.get("clicked")
    except:
        clicked = None
    print("clicked", clicked)      

    def create_pieces(x, direction):
        pieces = {}
        if direction == "top-to-bottom":
            for i in range (1, x+1):
                pieces[i] = [i]
        elif direction == "bottom-to-top":
            for i in range (1, x+1):
                pieces[i] = [x+1-i]
        else:
            return pieces
        return pieces

    #poistetaan klikattu pelinappula laudalta
    def remove_clicked(pieces, clicked):   
        if not clicked:
            return pieces
        key = str(clicked.split(":")[0])
        #TODO: tähän vielä se oikea clickedin poistaminen, kun ehditään sinne asti
        return pieces

    try:
        pieces = json.loads(request.values.get("pieces"))
        print("pieces ladattu jsonista")
        pieces = remove_clicked(pieces, clicked)
    except:
        #pieces luodaan annetun diagonaalisuunnan mukaan
        pieces = create_pieces(x, balls_direction)
        print("pieces luotiin annetun suunnan mukaan")
    print("pieces", pieces)

    #validoidaan lomakekenttien syötteet
    if request.method == 'POST':
        form.validate() 

    return Response(render_template("pohja.xhtml", form=form, pelaaja1=pelaaja1, pelaaja2=pelaaja2, x=x, first=first, pieces=pieces, pieces_json= json.dumps(pieces)), mimetype="application/xhtml+xml;charset=UTF-8") 