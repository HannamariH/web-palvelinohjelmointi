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
        pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="tietokantayhteydet",
                                                            pool_size=2,  # PythonAnywheren ilmaisen tunnuksen maksimi on kolme
                                                            **dbconfig)
        con = pool.get_connection()
        cur = con.cursor(buffered=True, dictionary=True)

        # TODO: hae tietokannasta kisat vuosineen

        sql = """SELECT kisanimi, alkuaika FROM kilpailut"""
        cur = con.cursor()
        cur.execute(sql)
        races = cur.fetchall()
        print(races)
        # TODO: käsittele kisat ja vuodet nättiin muotoon templatelle
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        race = request.form.get("race", "")
        m = hashlib.sha512()
        team_id = ""  # TODO: hae tietokannasta usernamen perusteella
        m.update(str(team_id).encode("UTF-8"))
        m.update(password.encode("UTF-8"))
        if m.hexdigest() == "tietokannasta haettu hash":
            # jos kaikki ok niin asetetaan sessioon tieto kirjautumisesta ja ohjataan laskurisivulle
            session['loggedin'] = "ok"
            # TODO: ohjaus halutulle sivulle
            return redirect(url_for('laskuri'))
        # jos ei ollut oikea salasana niin pysytään kirjautumissivulla.
        return render_template('login.xhtml', races=races)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Tunnus tai salasana on väärin")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Tietokantaa ei löydy")
        else:
            print(err)
    finally:
        con.close()
