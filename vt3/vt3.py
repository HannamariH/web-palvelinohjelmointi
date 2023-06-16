from flask import Flask, session, redirect, url_for, request, render_template
import hashlib
import io
import json
import urllib.parse
from functools import wraps
import mysql.connector
import mysql.connector.pooling
from mysql.connector import errorcode
from polyglot import PolyglotForm
from wtforms import StringField, PasswordField, SelectField, RadioField, BooleanField, validators, ValidationError
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
#TODO: csrf toimimaan!
#csrf = CSRFProtect(app)
app.secret_key = '7\xb9\x8b\xce\xff\x0feD/NA\xff\x818R\xc7\t\x00\xbcG\xf9S\xa0t'

file = io.open("dbconfig.json", encoding="UTF-8")
dbconfig = json.load(file)

try:
    pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="tietokantayhteydet",
                                                            pool_size=2,  # PythonAnywheren ilmaisen tunnuksen maksimi on kolme
                                                            **dbconfig)
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
    #jos lisätään uusi joukkue tai joukkueen nimeä on muokattu lomakkeella
    if not "team_name" in session.keys() or (field.data.lower() != session["team_name"].lower()):
        global pool
        try:
            con = pool.get_connection() 
            try:
                sql = """SELECT joukkue FROM joukkueet WHERE sarja = %s"""  
                cur = con.cursor()
                cur.execute(sql, (session["set_id"],))        
                teams = cur.fetchall()
                for team in teams:
                    if team[0].strip().lower() == field.data.strip().lower():
                        raise ValidationError("Sarjassa on jo samanniminen joukkue")
            except mysql.connector.errors.OperationalError:
                print("tietokantayhteyttä ei saada", err)
        finally:
            con.close()
    return

#tarkistaa, että joukkueelle syötetään vähintään kaksi jäsentä ja kaikilla jäsenillä on uniikki nimi
def validate_members(form, field):
    members = get_members_from_form(form)
    if len(members) < 2:
        raise ValidationError("Joukkueella on oltava vähintään 2 jäsentä")
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

def save_to_db(team, members, team_id, set_name, password=None):
        print(team, members)
        if password is not None:
            sql = "UPDATE joukkueet SET sarja = (SELECT sarjaid FROM sarjat WHERE kilpailu = %s AND sarja = %s), joukkue = %s, jasenet = %s, salasana = %s WHERE joukkueid = %s"
        else:
            sql = "UPDATE joukkueet SET sarja = (SELECT sarjaid FROM sarjat WHERE kilpailu = %s AND sarja = %s), joukkue = %s, jasenet = %s WHERE joukkueid = %s"
        
        global pool
        try:
            con = pool.get_connection() 
            try: 
                cur = con.cursor()
                try:
                    if password is not None:
                        cur.execute(sql, (session["race_id"], set_name, team, members, password, team_id))
                    else:
                        cur.execute(sql, (session["race_id"], set_name, team, members, team_id))
                    con.commit()
                    session["team_name"] = team
                except:
                    con.rollback()
                    print("ei voitu tallentaa kantaan")
                    #TODO: ilmoitus, ettei tietokantaan tallennus onnistunut
            except mysql.connector.errors.OperationalError:
                print("tietokantayhteyttä ei saada", err)
        finally:
            con.close()
        return

#------------ reitit alkavat -------------------

@app.route('/', methods=['GET'])
def redir():
    return redirect(url_for("signin"))

@app.route('/login', methods=['GET', 'POST'])
def signin():

    try:          
        session.clear()
        # haetaan kilpailut valikkoon
        global pool
        try:
            con = pool.get_connection() 
            try:
                sql = """SELECT kisa, alkuaika FROM kilpailut ORDER BY kisa, alkuaika""" 
                cur = con.cursor()
                cur.execute(sql)        
                races_init = cur.fetchall()
            except mysql.connector.errors.OperationalError:
                print("tietokantayhteyttä ei saada", err)
        finally:
            con.close()
    
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
        try:
            con = pool.get_connection() 
            try:
                sql = """SELECT j.joukkue, j.salasana, j.joukkueid, j.sarja, k.kisa, k.alkuaika, k.kisaid FROM joukkueet j, sarjat s, kilpailut k
                    WHERE lower(j.joukkue) = %s
                    AND k.kisa = %s
                    AND k.alkuaika like %s
                    AND j.sarja = s.sarjaid
                    AND s.kilpailu = k.kisaid"""
                cur = con.cursor()
                cur.execute(sql, (username, race_name, race_year+"%"))        
                team = cur.fetchall()
            except mysql.connector.errors.OperationalError:
                print("tietokantayhteyttä ei saada", err)
        finally:
            con.close()

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

@app.route('/teams', methods=['GET'])
@auth
def team_list():

    race_name = session["race_name"]
    race_year = session["race_year"]

    global pool
    try:
        con = pool.get_connection() 
        try:
            sql = """SELECT s.sarja, j.joukkue, j.jasenet FROM kilpailut k, joukkueet j, sarjat s 
                WHERE k.alkuaika LIKE %s AND k.kisa LIKE %s
                AND j.sarja = s.sarjaid
                AND s.kilpailu = k.kisaid
                ORDER BY s.sarja, j.joukkue COLLATE utf8mb4_swedish_ci;"""
            cur = con.cursor()
            cur.execute(sql, (race_year+"%", race_name))        
            teams = cur.fetchall()
        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()

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
    
    global pool
    try:
        con = pool.get_connection() 
        try:
            #haetaan ko. kisan sarjat valikkoon
            sql = """SELECT s.sarja FROM sarjat s
                WHERE s.kilpailu IN (
                SELECT k.kisaid FROM kilpailut k 
                WHERE k.kisa LIKE %s AND k.alkuaika LIKE %s) 
                ORDER BY s.sarja COLLATE utf8mb4_swedish_ci;"""
            cur = con.cursor()
            cur.execute(sql, (session["race_name"], session["race_year"]+"%"))        
            sarjat = cur.fetchall()

            #haetaan joukkueen tiedot valmiiksi lomakkeelle
            sql = """SELECT j.jasenet, s.sarja, s.kilpailu FROM joukkueet j, sarjat s 
                    WHERE j.sarja = s.sarjaid AND j.joukkue LIKE %s AND s.kilpailu = %s;"""
            cur = con.cursor()
            cur.execute(sql, (session["team_name"], session["race_id"]))
            team = cur.fetchall()
            sarja = team[0][1]
            members = team[0][0]
            members = members.replace("[","").replace("]","").replace('"',"").replace("'","")
            members_array = [x.strip() for x in members.split(",")]
        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()        
            
    class modifyTeamForm(PolyglotForm):
        #sarjavalikon oikeat arvot syötetään myöhemmin
        set = SelectField("Sarja", choices=(1,), coerce=str, validate_choice=False) #TODO: onko coerce tarpeen??
        team = StringField("Joukkueen nimi", [validate_team])   
        password = PasswordField("Salasana", []) 
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
            password = request.values.get("password")
            members = str(get_members_from_form(form))
            #salasana tallennetaan kantaan vain, jos se on syötetty kenttään
            print(members)
            if password:
                m = hashlib.sha512()
                m.update(str(session["team_id"]).encode("UTF-8"))
                m.update(password.encode("UTF-8"))  
                password = m.hexdigest()
                save_to_db(request.values.get("team").strip(), str(members), session["team_id"], request.values.get("set"), password)
            else:
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

#------------admin-puolen reitit-----------------------

@app.route('/admin/logout', methods=['GET'])
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

@app.route('/admin/races', methods=['GET'])
@auth_admin
def races():
    #haetaan tietokannasta joukkuelistaus aikajärjestyksessä
    global pool
    try:
        con = pool.get_connection() 
        try:
            sql = """SELECT kisa, alkuaika FROM kilpailut ORDER BY alkuaika;"""
            cur = con.cursor()
            cur.execute(sql,)
            races = cur.fetchall()
        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()

    #poistetaan alkuajoista kellonaika, luodaan enkoodattu url-parametri
    races_with_dates = []
    for race in races:
        race_date = race[1].date()
        race_for_url = urllib.parse.quote(race[0] + " " + str(race_date))
        races_with_dates.append((race[0], race_date, race_for_url))
    return render_template("admin_races.xhtml", races=races_with_dates)

#näyttää valitun kilpailut sarjat
@app.route('/admin/<race>/sets', methods=['GET'])
@auth_admin
def sets(race):
    #erotetaan toisistaan kisan nimi ja alkuaika
    race_list = race.split()
    race_name = race_list[0]
    race_date = race_list[1]

    global pool
    try:
        con = pool.get_connection() 
        try:
            #haetaan k.kisaid, joka tallennetaan session["race_id"]:hen
            sql = """SELECT k.kisaid FROM kilpailut k WHERE k.kisa LIKE %s and k.alkuaika LIKE %s"""
            cur = con.cursor()
            cur.execute(sql,(race_name, race_date+"%"))
            race_id = cur.fetchall()[0][0]
            #race_id sessioon, jos se muuttui
            if not "race_id" in session.keys() or ("race_id" in session.keys() and session["race_id"] != race_id):
                session["race_id"] = race_id
                #nämä popataan pois VAIN, jos race vaihtuu
                session.pop("set_id", None)
                session.pop("set_name", None)
                session.pop("team_name", None)
            #haetaan ko. kisan sarjat
            sql = """SELECT sarja FROM sarjat WHERE kilpailu LIKE %s ORDER BY sarja COLLATE utf8mb4_swedish_ci"""
            cur = con.cursor()
            cur.execute(sql,(race_id,))
            sets = cur.fetchall()
        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()
    
    team = None
    if "team_name" in session.keys():
        team = session["team_name"]
    set = None
    if "set_name" in session.keys():
        set = session["set_name"]
    return render_template("admin_sets.xhtml", sets=sets, race=race, team=team, set=set)

@app.route('/admin/<race>/<set>/teams', methods=['GET', 'POST'])
@auth_admin
def teams(race, set):
    global pool
    try:
        con = pool.get_connection() 
        try:
            #haetaan kilpailun ja sarjan id:t
            race_list = race.split()
            race_name = race_list[0]
            race_date = race_list[1]
            sql = """SELECT s.sarjaid, k.kisaid FROM sarjat s
                JOIN kilpailut k ON s.kilpailu = k.kisaid
                WHERE k.kisa LIKE %s AND k.alkuaika LIKE %s AND s.sarja LIKE %s"""
            cur = con.cursor()
            cur.execute(sql, (race_name, race_date+"%", set))
            result = cur.fetchall()
            set_id = result[0][0]
            race_id = result[0][1]

        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()

    #jos kisa tai sarja on vaihtunut, poistetaan joukkue sessiosta
    if ("set_id" in session.keys() and session["set_id"] != set_id) or ("race_id" in session.keys() and session["race_id"] != race_id):
        print("poistetaan joukkue sessiosta, saisko tehdä niin?")
        session.pop("team_name", None)
    session["race_id"] = race_id
    session["set_id"] = set_id  
    session["set_name"] = set

    try:
        con = pool.get_connection() 
        try:
            sql = """SELECT joukkue, sarja FROM joukkueet 
                WHERE sarja IN (SELECT sarjaid FROM sarjat WHERE kilpailu = %s and sarja = %s) 
                ORDER BY joukkue COLLATE utf8mb4_swedish_ci"""
            cur = con.cursor()
            cur.execute(sql,(race_id, set))
            teams = cur.fetchall()
            teams = [team[0] for team in teams] 
        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()   

    #TODO: pitäiskö tiimien nimet (ja kilpailut taas) urlenkoodata??

    class adminAddTeamForm(PolyglotForm):
        #sarjavalikon oikeat arvot syötetään myöhemmin
        team = StringField("Joukkueen nimi", [validate_team])   
        password = PasswordField("Salasana", []) 
        member1 = StringField("Jäsen 1", [validate_members])
        member2 = StringField("Jäsen 2")
        member3 = StringField("Jäsen 3")
        member4 = StringField("Jäsen 4")
        member5 = StringField("Jäsen 5")

    if request.method == "POST":
        form = adminAddTeamForm()
        isValid = form.validate()
        if isValid:
            #tallennetaan joukkue tietokantaan
            team = request.values.get("team").strip()
            members = str(get_members_from_form(form))
            try:
                con = pool.get_connection() 
                try:
                    sql = "INSERT INTO joukkueet (joukkue, sarja, jasenet) VALUES (%s, %s, %s)"
                    cur = con.cursor()
                    try:
                        cur.execute(sql, (team, session["set_id"], members))
                        con.commit()
                        session["team_name"] = team 
                        #salasanan lisäys kantaan juuri lisätylle joukkueelle
                        try:
                            password = request.values.get("password").strip()
                            if password == "":
                                password = "ties4080"
                        except:
                            password = "ties4080"
                        #TODO: tehtävänannossa SELECT LAST_INSERT_ID(), onko muutettava vai kelpaako?
                        team_id = cur.lastrowid
                        m = hashlib.sha512()
                        m.update(str(team_id).encode("UTF-8"))
                        m.update(password.encode("UTF-8"))  
                        password = m.hexdigest()
                        sql = "UPDATE joukkueet SET salasana = %s WHERE joukkueid = %s"
                        cur = con.cursor()
                        try:
                            cur.execute(sql, (password, team_id))
                            con.commit()
                            #lisätään uusi joukkue joukkuelistaan
                            teams.append(team)
                            teams.sort()
                            return render_template("admin_teams.xhtml", form=form, teams=teams, race=race, set=set)
                        except:
                            con.rollback()
                            #TODO: ilmoitus, ettei tietokantaan tallennus onnistunut?
                    except:
                        con.rollback()
                        #TODO: ilmoitus, ettei tietokantaan tallennus onnistunut?
                except mysql.connector.errors.OperationalError:
                    print("tietokantayhteyttä ei saada", err)
            finally:
                con.close()

    elif request.method == "GET" and request.args:
        form = adminAddTeamForm(request.args)
    else:
        form = adminAddTeamForm()

    team = None
    if "team_name" in session.keys():
        team = session["team_name"]

    return render_template("admin_teams.xhtml", form=form, teams=teams, race=race, set=set, team=team)

@app.route('/admin/<race>/<team>', methods=['GET', 'POST'])
@auth_admin
def team(race, team):
    session["team_name"] = team
    race_list = race.split()
    race_name = race_list[0]
    race_date = race_list[1]

    global pool
    try:
        con = pool.get_connection() 
        try:
            #haetaan ko. kisan sarjat radiopainikevalikkoon
            sql = """SELECT s.sarja FROM sarjat s
                    WHERE s.kilpailu IN (
                        SELECT k.kisaid FROM kilpailut k 
                        WHERE k.kisa LIKE %s AND k.alkuaika LIKE %s) 
                    ORDER BY s.sarja COLLATE utf8mb4_swedish_ci;"""
            cur = con.cursor()
            cur.execute(sql, (race_name, race_date+"%"))        
            sarjat = cur.fetchall()

            #haetaan joukkueen tiedot valmiiksi lomakkeelle
            sql = """SELECT j.jasenet, s.sarja, s.kilpailu, j.joukkueid FROM joukkueet j, sarjat s 
                    WHERE j.sarja = s.sarjaid AND j.joukkue LIKE %s AND s.kilpailu = %s;"""
            cur = con.cursor()
            cur.execute(sql, (team, session["race_id"]))
            team_data = cur.fetchall()
        except mysql.connector.errors.OperationalError:
            print("tietokantayhteyttä ei saada", err)
    finally:
        con.close()

    session["team_id"] = team_data[0][3]
    sarja = team_data[0][1]
    members = team_data[0][0]
    members = members.replace("[","").replace("]","").replace('"',"").replace("'","")
    members_array = [x.strip() for x in members.split(",")]
    race_id = team_data[0][2]    

    class adminModifyTeamForm(PolyglotForm):
        #sarjavalikon oikeat arvot syötetään myöhemmin
        team = StringField("Joukkueen nimi", [validate_team])
        password = PasswordField("Salasana", []) 
        set = RadioField("Sarja", choices=(1,), validate_choice=False)
        member1 = StringField("Jäsen 1", [validate_members])
        member2 = StringField("Jäsen 2")
        member3 = StringField("Jäsen 3")
        member4 = StringField("Jäsen 4")
        member5 = StringField("Jäsen 5")
        remove = BooleanField("Poista joukkue")

    if request.method == "POST":
        #ensin mahdollinen poistaminen
        if request.values.get("remove") == "y":
            try:
                con = pool.get_connection() 
                #selvitetään, onko joukkueella rastileimauksia
                try:
                    sql = """SELECT rasti FROM tupa JOIN joukkueet ON tupa.joukkue = joukkueet.joukkueid WHERE joukkueet.joukkueid = %s"""
                    cur = con.cursor()
                    cur.execute(sql, (session["team_id"],))
                    cps = cur.fetchall()
                except mysql.connector.errors.OperationalError:
                    print("tietokantayhteyttä ei saada", err)

                if len(cps) > 0:
                    cannot_delete = "Joukkuetta ei voida poistaa, koska sillä on rastileimauksia."
                    form = adminModifyTeamForm()
                    #tietokannasta haettujen sarjojen asetus lomakekenttään
                    form.set.choices = [(i[0], i[0]) for i in sarjat]                
                    #oikean sarjan asetus valituksi
                    try:
                        form.set.data = request.values.get("set")
                        if not form.set.data:
                            form.set.data = sarja
                    except:
                        pass
                    return render_template("admin_team.xhtml", form=form, team=team, race=race, set=sarja, cannot_delete=cannot_delete)
                else:
                    try:
                        sql = """DELETE FROM joukkueet WHERE joukkueid = %s"""
                        cur = con.cursor()
                        cur.execute(sql, (session["team_id"],))
                        con.commit()
                        #joukkueen tiedot pois sessiosta
                        session.pop("team_id", None)
                        session.pop("team_name", None)
                    except mysql.connector.errors.OperationalError:
                        print("tietokantayhteyttä ei saada", err)
            finally:
                con.close()        
            return redirect(url_for('teams', race=race, set=session["set_name"]))
        #sitten joukkueen muokkaaminen
        else:
            form = adminModifyTeamForm()
            isValid = form.validate()
            if isValid:
                members = str(get_members_from_form(form))
                password = request.values.get("password")
                #salasana tallennetaan kantaan vain, jos se on syötetty kenttään
                if password:
                    m = hashlib.sha512()
                    m.update(str(session["team_id"]).encode("UTF-8"))
                    m.update(password.encode("UTF-8"))  
                    password = m.hexdigest()
                    save_to_db(request.values.get("team").strip(), members, session["team_id"], request.values.get("set"), password)
                else:
                    save_to_db(request.values.get("team").strip(), members, session["team_id"], request.values.get("set"))
    elif request.method == "GET" and request.args:
        form = adminModifyTeamForm(request.args)
    else:
        form = adminModifyTeamForm() 

    #tietokannasta haettujen sarjojen asetus lomakekenttään
    form.set.choices = [(i[0], i[0]) for i in sarjat]

    #oikean sarjan asetus valituksi
    try:
        form.set.data = request.values.get("set")
        if not form.set.data:
            form.set.data = sarja
    except:
        pass

    try:
        if request.method == "GET":
            form.team.data = team
        else:
            form.team.data = request.values.get("team").strip()
            if form.team.data == "":
                form.team.data = form.team.data
            elif not form.team.data:
                form.team.data = team
    except:
        #TODO: jotain
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

    return render_template("admin_team.xhtml", form=form, team=team, race=race, set=sarja)