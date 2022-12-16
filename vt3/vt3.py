from flask import Flask, session, redirect, url_for, escape, request, Response, render_template
import hashlib
import io
import json
from functools import wraps
import mysql.connector
import mysql.connector.pooling
from mysql.connector import errorcode
from polyglot import PolyglotForm
from wtforms import StringField, RadioField, validators
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
#csrf = CSRFProtect(app)
app.secret_key = '7\xb9\x8b\xce\xff\x0feD/NA\xff\x818R\xc7\t\x00\xbcG\xf9S\xa0t'

file = io.open("dbconfig.json", encoding="UTF-8")
dbconfig = json.load(file)

try:
    pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="tietokantayhteydet",
                                                            pool_size=2,  # PythonAnywheren ilmaisen tunnuksen maksimi on kolme
                                                            **dbconfig)
    con = pool.get_connection()    
except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Tunnus tai salasana on väärin")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Tietokantaa ei löydy")
        else:
            print(err)

#TODO: tarkista, että tietokantayhteys tulee suljettua aina lopuksi!
#miten tehdään, kun eri reitit käyttää samaa yhteyttä? vain logout-reittiin con.close()?

def auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not "loggedin" in session:
            return redirect(url_for("signin"))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def signin():

    try:          
        session.clear()
        # haetaan kilpailut valikkoon
        sql = """SELECT kisanimi, alkuaika FROM kilpailut"""
        cur = con.cursor()
        #cur = con.cursor(buffered=True, dictionary=True)
        cur.execute(sql)
        races_init = cur.fetchall()
        races = []
        for i in races_init:
            race = i[0]
            year = i[1].timetuple().tm_year
            race = f"{race} {str(year)}"
            races.append(race)
        login_error = False
        username = request.form.get("username", "")
        username = username.strip().lower()
        race = request.form.get("race", "")
        try:
            race_name = race.split()[0]
            race_year = race.split()[1]
        except:
            race_name = ""
            race_year = ""
        # haetaan annettujen joukkueen ja kilpailun tiedot
        sql = """SELECT j.joukkuenimi, j.salasana, j.id, k.kisanimi, k.alkuaika FROM joukkueet j, sarjat s, kilpailut k
                WHERE lower(j.joukkuenimi) = %s
                AND k.kisanimi = %s
                AND k.alkuaika like %s
                AND j.sarja = s.id
                AND s.kilpailu = k.id"""
        cur = con.cursor()
        cur.execute(sql, (username, race_name, race_year+"%"))        
        team = cur.fetchall()
        if team == []:
            session.clear()
            klikattu = request.form.get("kirjaudu", "")           
            if klikattu != "":
                login_error = True        
        password = request.form.get("password", "")   
        m = hashlib.sha512()
        try:
            m.update(str(team[0][2]).encode("UTF-8"))
            m.update(password.encode("UTF-8"))
            if m.hexdigest() == team[0][1]:
                session['loggedin'] = "ok"
                session["team_name"] = team[0][0]
                session["start_time"] = team[0][4]
                session["race_name"] = race_name
                session["race_year"] = race_year
                print(session)
                return redirect(url_for('team_list'))
            # jos ei ollut oikea salasana, pysytään kirjautumissivulla
            session.clear()
            return render_template('login.xhtml', races=races, login_error=login_error)
        except:
            session.clear()
            return render_template('login.xhtml', races=races, login_error=login_error)
    except:
        #TODO pass????
        pass
    #finally:
    #    con.close()

#TODO: pitäiskö olla molemmat metodit sallittu? 
# redirect(url_for) tekee aina(?) GET-pyynnön
@app.route('/teams', methods=['GET'])
@auth
def team_list():

    race_name = session["race_name"]
    race_year = session["race_year"]

    sql = """SELECT s.sarjanimi, j.joukkuenimi, j.jasenet FROM kilpailut k, joukkueet j, sarjat s 
        WHERE k.alkuaika LIKE %s AND k.kisanimi LIKE %s
        AND j.sarja = s.id
        AND s.kilpailu = k.id
        ORDER BY s.sarjanimi, j.joukkuenimi;"""
    cur = con.cursor()
    cur.execute(sql, (race_year+"%", race_name))        
    teams = cur.fetchall()
    teams_list = []
    for team in teams:
        members = team[2]
        members = members.replace("[","").replace("]","").replace('"',"")
        members_array = [x.strip() for x in members.split(",")]
        team_list = list(team)
        team_list[2] = members_array
        teams_list.append(team_list)

    return render_template('teamslist.xhtml', race_name=race_name, race_year=race_year, teams=teams_list, start_time=session["start_time"], team_name=session["team_name"])

@app.route('/modify', methods=['GET', 'POST'])
@auth
def modify_team():
    #haetaan ko. kisan sarjat radiobuttoneihin
    sql = """SELECT s.sarjanimi FROM sarjat s 
            WHERE s.kilpailu IN (
                SELECT k.id FROM kilpailut k 
                WHERE k.kisanimi LIKE %s AND k.alkuaika LIKE %s) 
            ORDER BY s.sarjanimi;"""
    cur = con.cursor()
    cur.execute(sql, (session["race_name"], session["race_year"]+"%"))        
    sarjat = cur.fetchall()

    #haetaan joukkueen tiedot valmiiksi lomakkeelle
    sql = """SELECT j.jasenet, s.sarjanimi FROM joukkueet j, sarjat s 
            WHERE j.sarja = s.id AND j.joukkuenimi LIKE %s;"""
    cur = con.cursor()
    cur.execute(sql, (session["team_name"],))        
    team = cur.fetchall()
    sarja = team[0][1]
    members = team[0][0]
    members = members.replace("[","").replace("]","").replace('"',"")
    members_array = [x.strip() for x in members.split(",")]

    #TODO: lomake
    class modifyTeamForm(PolyglotForm):
        #radiobuttonien oikeat arvot syötetään myöhemmin
        set = RadioField("Sarja", choices=(1,), coerce=str, validate_choice=False) #TODO: onko coerce tarpeen??
        #TODO: samassa sarjassa ei saa olla kahta samannimistä joukkuetta, missä vaiheessa tarkistus?
        team = StringField("Joukkueen nimi", validators=[validators.InputRequired(
            message="Syötä joukkueen nimi"), validators.Length(min=1, message="Syötä joukkueen nimi")])   
        member1 = StringField("Jäsen 1")
        member2 = StringField("Jäsen 2")
        member3 = StringField("Jäsen 3")
        member4 = StringField("Jäsen 4")
        member5 = StringField("Jäsen 5")

    if request.method == "POST":
        form = modifyTeamForm()
        form.validate()
    elif request.method == "GET" and request.args:
        form = modifyTeamForm(request.args)
        form.validate()
    else:
        form = modifyTeamForm()

    form.set.choices = [(i[0], i[0]) for i in sarjat]

    try:
        form.team.data = request.values.get("team")
        if not form.team.data:
            form.team.data = session["team_name"]
    except:
        #TODO: jotain
        pass

    try:
        form.set.data = request.values.get("set")
        if not form.set.data:
            form.set.data = sarja
    except:
        pass

    try:
        form.member1.data = request.values.get("member1")
        if not form.member1.data:
            form.member1.data = members_array[0]
    except:
        form.member1.data = ""

    try:
        form.member2.data = request.values.get("member2")
        if not form.member2.data:
            form.member2.data = members_array[1]
    except:
        form.member2.data = ""

    try:
        form.member3.data = request.values.get("member3")
        if not form.member3.data:
            form.member3.data = members_array[2]
    except:
        form.member3.data = ""

    try:
        form.member4.data = request.values.get("member4")
        if not form.member4.data:
            form.member4.data = members_array[3]
    except:
        form.member4.data = ""

    try:
        form.member5.data = request.values.get("member5")
        if not form.member5.data:
            form.member5.data = members_array[4]
    except:
        form.member5.data = ""

    return render_template("modify.xhtml", form=form, team=team, sarjat=sarjat, sarja=sarja, members=members_array, race_name=session["race_name"], race_year=session["race_year"], start_time=session["start_time"], team_name=session["team_name"])