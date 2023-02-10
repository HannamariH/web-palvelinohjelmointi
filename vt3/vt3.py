from flask import Flask, session, redirect, url_for, escape, request, Response, render_template
import hashlib
import io
import json
import urllib.parse
from functools import wraps
import mysql.connector
import mysql.connector.pooling
from mysql.connector import errorcode
from polyglot import PolyglotForm
from wtforms import StringField, RadioField, SelectField, validators, ValidationError
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

def auth_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not "admin" in session:
            return redirect(url_for("login_admin"))
        return f(*args, **kwargs)
    return decorated

#tarkistaa, ettei joukkueen nimi ole tyhjä ja ettei samannimistä joukkuetta vielä ole ko. sarjassa
def validate_team(form, field):
    field.data = field.data.strip()
    if not field.data:
        raise ValidationError("Joukkueen nimi ei saa olla tyhjä")
    #jos joukkueen nimeä on muokattu lomakkeella
    if field.data.lower() != session["team_name"].lower():
        sql = """SELECT joukkuenimi FROM joukkueet WHERE sarja = %s"""  
        cur = con.cursor()
        cur.execute(sql, (session["set_id"],))        
        teams = cur.fetchall()
        for team in teams:
            if team[0].strip().lower() == field.data.strip().lower():
                raise ValidationError("Sarjassa on jo samanniminen joukkue")
    return

#tarkistaa, että joukkueelle syötetään vähintään kaksi jäsentä ja kaikilla jäsenillä on uniikki nimi
def validate_members(form, field):
    members = get_members_from_form(form)
    if len(members) < 2:
        raise ValidationError("Joukkueella oltava vähintään 2 jäsentä")
    if len(members) != len(set(map(str.lower, members))):
        raise ValidationError("Joukkueen jäsenten nimien on oltava uniikkeja")

#hakee lomakkeelta jäsenet listaan
def get_members_from_form(form):
    members = []
    for i in form.data.items():
        if "member" in i[0]:
            members.append(i[1].strip())
        while '' in members:
            members.remove('')
    return members

@app.route('/', methods=['GET'])
def redir():
    return redirect(url_for("signin"))

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
        races = ["--Valitse kilpailu--"]
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
        sql = """SELECT j.joukkuenimi, j.salasana, j.id, j.sarja, k.kisanimi, k.alkuaika, k.id FROM joukkueet j, sarjat s, kilpailut k
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
                session["team_id"] = team[0][2]
                session["set_id"] = team[0][3]
                #poistetaan datetimestä kellonaika, pelkkä päiväys riittää
                session["start_time"] = str(team[0][5]).split()[0]
                session["race_name"] = race_name
                session["race_year"] = race_year
                session["race_id"] = team[0][6]
                return redirect(url_for('team_list'))
            # jos ei ollut oikea salasana, pysytään kirjautumissivulla
            session.clear()
            return render_template('login.xhtml', races=races, login_error=login_error)
        except:
            session.clear()
            return render_template('login.xhtml', races=races, login_error=login_error)
    except:
        #TODO pass????
        session.clear()
        return render_template('login.xhtml', races=races, login_error=login_error)
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
    #tehdään merkkijonomuotoisesta jäsenkentästä järjestetty lista
    teams_list = []
    for team in teams:
        members = team[2]
        members = members.replace("[","").replace("]","").replace('"',"").replace("'","")
        #järjestää jäsenarrayn aakkosjärjestykseen kirjainkoosta välittämättä
        members_array = sorted([x.strip() for x in members.split(",")], key=str.casefold)
        team_list = list(team)
        team_list[2] = members_array
        teams_list.append(team_list)

    return render_template('teamslist.xhtml', race_name=race_name, race_year=race_year, teams=teams_list, start_time=session["start_time"], team_name=session["team_name"])

@app.route('/modify', methods=['GET', 'POST'])
@auth
def modify_team():
    #haetaan ko. kisan sarjat valikkoon
    sql = """SELECT s.sarjanimi FROM sarjat s
            WHERE s.kilpailu IN (
                SELECT k.id FROM kilpailut k 
                WHERE k.kisanimi LIKE %s AND k.alkuaika LIKE %s) 
            ORDER BY s.sarjanimi;"""
    cur = con.cursor()
    cur.execute(sql, (session["race_name"], session["race_year"]+"%"))        
    sarjat = cur.fetchall()

    #haetaan joukkueen tiedot valmiiksi lomakkeelle
    sql = """SELECT j.jasenet, s.sarjanimi, s.kilpailu FROM joukkueet j, sarjat s 
            WHERE j.sarja = s.id AND j.joukkuenimi LIKE %s;"""
    cur = con.cursor()
    cur.execute(sql, (session["team_name"],))
    team = cur.fetchall()
    sarja = team[0][1]
    members = team[0][0]
    members = members.replace("[","").replace("]","").replace('"',"").replace("'","")
    members_array = [x.strip() for x in members.split(",")]
    race_id = team[0][2]    

    def save_to_db(team, members, team_id, set_name):
        sql = "UPDATE joukkueet SET sarja = (SELECT id FROM sarjat WHERE kilpailu = %s AND sarjanimi = %s), joukkuenimi = %s, jasenet = %s WHERE id = %s"
        cur = con.cursor()
        try:
            cur.execute(sql, (session["race_id"], set_name, team, members, team_id))
            con.commit()
            session["team_name"] = team
        except:
            con.rollback()
            #TODO: ilmoitus, ettei tietokantaan tallennus onnistunut
        return
            
    class modifyTeamForm(PolyglotForm):
        #sarjavalikon oikeat arvot syötetään myöhemmin
        set = SelectField("Sarja", choices=(1,), coerce=str, validate_choice=False) #TODO: onko coerce tarpeen??
        team = StringField("Joukkueen nimi", [validate_team])   
        member1 = StringField("Jäsen 1", [validate_members])
        member2 = StringField("Jäsen 2")
        member3 = StringField("Jäsen 3")
        member4 = StringField("Jäsen 4")
        member5 = StringField("Jäsen 5")

    if request.method == "POST":
        form = modifyTeamForm()
        isValid = form.validate()
        if isValid:
            #kantaan tallennus
            members = get_members_from_form(form)
            save_to_db(request.values.get("team").strip(), str(members), session["team_id"], request.values.get("set"))
    elif request.method == "GET" and request.args:
        form = modifyTeamForm(request.args)
    else:
        form = modifyTeamForm()

    #lomakkeen tietojen täyttäminen
    form.set.choices = [(i[0], i[0]) for i in sarjat]

    try:
        if request.method == "GET":
            form.team.data = session["team_name"]
        else:
            form.team.data = request.values.get("team").strip()
            if form.team.data == "":
                form.team.data = form.team.data
            elif not form.team.data:
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
        if request.method == "GET":
            form.member1.data = members_array[0]
        else: 
            form.member1.data = request.values.get("member1").strip()
            if form.member1.data == "":
                form.member1.data = form.member1.data
            elif not form.member1.data:
                form.member1.data = members_array[0]
    except:
        form.member1.data = ""

    try:
        if request.method == "GET":
            form.member2.data = members_array[1]
        else:
            form.member2.data = request.values.get("member2").strip()
            if form.member2.data == "":
                form.member2.data = form.member2.data
            elif not form.member2.data:
                form.member2.data = members_array[1]
    except:
        form.member2.data = ""

    try:
        if request.method == "GET":
            form.member3.data = members_array[2]
        else:
            form.member3.data = request.values.get("member3").strip()
            if form.member3.data == "":
                form.member3.data = form.member3.data
            elif not form.member3.data:
                form.member3.data = members_array[2]
    except:
        form.member3.data = ""

    try:
        if request.method == "GET":
            form.member4.data = members_array[3]
        else:
            form.member4.data = request.values.get("member4").strip()
            if form.member4.data == "":
                form.member4.data = form.member4.data
            elif not form.member4.data:
                form.member4.data = members_array[3]
    except:
        form.member4.data = ""

    try:
        if request.method == "GET":
            form.member5.data = members_array[4]
        else:
            form.member5.data = request.values.get("member5").strip()
            if form.member5.data == "":
                form.member5.data = form.member5.data
            elif not form.member5.data:
                form.member5.data = members_array[4]
    except:
        form.member5.data = ""

    return render_template("modify.xhtml", form=form, team=team, sarjat=sarjat, sarja=sarja, members=members_array, race_name=session["race_name"], race_year=session["race_year"], start_time=session["start_time"], team_name=session["team_name"])

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for("signin"))

@app.route('/admin_logout', methods=['GET'])
def admin_logout():
    session.clear()
    return redirect(url_for("login_admin"))

@app.route('/admin', methods=['GET', 'POST'])
def login_admin():
    session.clear()
    password = request.form.get("password", "")   
    username = request.form.get("username", "") 
    m = hashlib.sha512()
    try:
        m.update(password.encode("UTF-8"))
        m.update(username.encode("UTF-8"))
        if m.hexdigest() == "8450eca01665516d9aeb5317764902b78495502637c96192c81b1683d32d691a0965cf037feca8b9ed9ee6fc6ab8f27fce8f77c4fd9b4a442a00fc317b8237e6":
            session['admin'] = True
            return redirect(url_for('races'))
        # jos ei ollut oikea salasana, pysytään kirjautumissivulla
        return render_template('admin_login.xhtml')
    except:
        return render_template('admin_login.xhtml')

@app.route('/admin_races', methods=['GET', 'POST'])
@auth_admin
def races():
    #haetaan tietokannasta joukkuelistaus aikajärjestyksessä
    sql = """SELECT kisanimi, alkuaika FROM kilpailut ORDER BY alkuaika;"""
    cur = con.cursor()
    cur.execute(sql,)
    races = cur.fetchall()
    #poistetaan alkuajoista kellonaika, luodaan enkoodattu url-parametri
    races_with_dates = []
    for race in races:
        race_date = race[1].date()
        race_for_url = urllib.parse.quote(race[0] + " " + str(race_date))
        races_with_dates.append((race[0], race_date, race_for_url))
    return render_template("admin_races.xhtml", races=races_with_dates)

@app.route('/admin/<race>/sets', methods=['GET', 'POST'])
@auth_admin
def sets(race):
    session["race"] = race
    #erotetaan toisistaan kisan nimi ja alkuaika
    race_list = race.split()
    race_name = race_list[0]
    race_date = race_list[1]
    #haetaan ko. kisan sarjat
    sql = """SELECT s.sarjanimi FROM sarjat s WHERE s.kilpailu in (SELECT k.id FROM kilpailut k WHERE k.kisanimi LIKE %s and k.alkuaika LIKE %s) ORDER BY s.sarjanimi"""
    cur = con.cursor()
    cur.execute(sql,(race_name, race_date+"%"))
    sets = cur.fetchall()
    return render_template("admin_sets.xhtml", sets=sets, race=race)

@app.route('/admin/<race>/<set>/teams', methods=['GET', 'POST'])
@auth_admin
def teams(race, set):
    #TODO: hae ko. kisan ja sarjan joukkueet

    class adminAddTeamForm(PolyglotForm):
        #sarjavalikon oikeat arvot syötetään myöhemmin
        team = StringField("Joukkueen nimi", [validate_team])   
        password = StringField("Salasana", []) 
        member1 = StringField("Jäsen 1", [validate_members])
        member2 = StringField("Jäsen 2")
        member3 = StringField("Jäsen 3")
        member4 = StringField("Jäsen 4")
        member5 = StringField("Jäsen 5")

    return render_template("admin_teams.xhtml")

@app.route('/admin/<team>', methods=['GET', 'POST'])
@auth_admin
def team(team):
    return render_template("admin_team.xhtml")