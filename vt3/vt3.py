from flask import Flask, session, redirect, url_for, escape, request, Response, render_template
import hashlib
import io
import json
from functools import wraps
import mysql.connector
import mysql.connector.pooling
from mysql.connector import errorcode

app = Flask(__name__)

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
            session.pop("loggedin", None)
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
                return redirect(url_for('team_list', race_name=race_name, race_year=race_year))
            # jos ei ollut oikea salasana, pysytään kirjautumissivulla
            session.pop("loggedin", None)
            return render_template('login.xhtml', races=races, login_error=login_error)
        except:
            session.pop("loggedin", None)
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
    race_name=request.args.get("race_name")
    race_year=request.args.get("race_year")

    sql = """SELECT s.sarjanimi, j.joukkuenimi, j.jasenet FROM kilpailut k, joukkueet j, sarjat s 
        WHERE k.alkuaika LIKE %s AND k.kisanimi LIKE %s
        AND j.sarja = s.id
        AND s.kilpailu = k.id
        ORDER BY s.sarjanimi, j.joukkuenimi;"""
    cur = con.cursor()
    cur.execute(sql, (race_year+"%", race_name))        
    teams = cur.fetchall()
    print(teams)

    return render_template('teamslist.xhtml', race_name=race_name, race_year=race_year, teams=teams)
