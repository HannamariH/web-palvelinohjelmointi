from flask import Flask, Response, request, render_template
from flask_wtf.csrf import CSRFProtect
from polyglot import PolyglotForm
from wtforms import IntegerField, StringField, validators, IntegerField, ValidationError
app = Flask(__name__)

csrf = CSRFProtect(app)
app.secret_key = 'a"\xf9$T\x88\xefT8[\xf1\xc4Y-r@\t\xec!5d\xf9\xcc\xa2\xaa'



@app.route('/', methods=["GET", "POST"])
def chess():

    class ChessForm(PolyglotForm):
        x = IntegerField('Laudan koko', validators=[validators.InputRequired(message="Syöttämäsi arvo ei kelpaa"), validators.NumberRange(min=8,max=16, message="Syöttämäsi arvo ei kelpaa")])
        pelaaja1 = StringField('Pelaaja 1', validators=[validators.InputRequired(message="Syötä pelaajan nimi"), validators.Length(min=1, message="Syötä pelaajan nimi")])
        pelaaja2 = StringField("Pelaaja 2", validators=[validators.InputRequired(message="Syötä pelaajan nimi"), validators.Length(min=1, message="Syötä pelaajan nimi")])

    form = ChessForm()

    try:
        pelaaja1 = request.values.get("pelaaja1")
        #if not pelaaja1:
        #    pelaaja1 = request.values.get("prev_p1")
        if not pelaaja1:
            pelaaja1 = "Pelaaja 1"
    except:
        pelaaja1 = "Pelaaja 1"

    try:
        pelaaja2 = request.values.get("pelaaja2")
        #if not pelaaja2:
        #    pelaaja2 = request.values.get("prev_p2")
        if not pelaaja2:
            pelaaja2 = "Pelaaja 2"
    except:
        pelaaja2 = "Pelaaja 2"

    try:
        x = int(request.values.get("x"))
        #if not x:
        #    x = int(request.values.get("prev_x"))
        if x < 8 or x > 16:
            x = 8
    except:
        x = 8

    if request.method == 'POST':
        form.validate()

    return Response(render_template("pohja.xhtml", form=form, pelaaja1=pelaaja1, pelaaja2=pelaaja2, x=x), mimetype="application/xhtml+xml;charset=UTF-8") 