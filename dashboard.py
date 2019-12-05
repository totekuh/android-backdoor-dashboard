#!/usr/bin/env python3
import sqlite3

from flask import Flask, render_template, redirect, url_for
from flask_apscheduler import APScheduler


SQL_INSERT = {
    "sms": """
    INSERT INTO sms (type, date, address, status, message)
    SELECT :Type, :Date, :Address, :Status, :Message
    WHERE NOT EXISTS(SELECT 1 FROM sms WHERE type =:Type AND date =:Date AND address =:Address AND status =:Status AND message =:Message );""",
    "calls": """
    INSERT INTO calls (type, date, number, name, duration)
    SELECT :Type, :Date, :Number, :Name, :Duration
    WHERE NOT EXISTS(SELECT 1 FROM calls WHERE type =:Type AND date =:Date AND number =:Number AND name =:Name AND duration =:Duration );""",
    "contacts": """
    INSERT INTO contacts (number, name)
    SELECT :Number, :Name
    WHERE NOT EXISTS(SELECT 1 FROM contacts WHERE number =:Number AND name =:Name );""",
}


class Config(object):
    SCHEDULER_API_ENABLED = True
    DB = "dump.db"


scheduler = APScheduler()
app = Flask(__name__, template_folder="")
app.config.from_object(Config())


@scheduler.task('interval', id='dump_update', seconds=10, misfire_grace_time=900)
def dump_update():
    db = app.config['DB']

    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS sms (type TEXT, date TEXT, address TEXT, status TEXT, message TEXT);")
        conn.execute("CREATE TABLE IF NOT EXISTS calls (type TEXT, date TEXT, number TEXT, name TEXT, duration TEXT);")
        conn.execute("CREATE TABLE IF NOT EXISTS contacts (number TEXT, name TEXT);")

    requested_dumps = ["sms", "calls", "contacts"]
    for dump_type in requested_dumps:
        meta = {'DumpType': dump_type}
        headers = []
        dump = {}
        try:
            with open(f"{dump_type}.txt", 'r', encoding='utf-8') as dump_f:
                idx = None
                while True:
                    line = next(dump_f).strip()
                    if line:
                        if line[0] == "#":
                            idx = line
                            dump[idx] = {}
                        elif idx:
                            key, value = [s.strip() for s in line.split(":", maxsplit=1)]
                            dump[idx][key] = value
                            if key not in headers:
                                headers.append(key)
                        elif ":" in line:
                            key, value = [s.strip() for s in line.split(":", maxsplit=1)]
                            meta[key] = value
        except StopIteration:
            dump = list(dump.values())

        with sqlite3.connect(db) as conn:
            for row in dump:
                conn.execute(SQL_INSERT[dump_type], row)
    print('Dump!')


@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    dumps = {}
    with sqlite3.connect(app.config['DB']) as conn:
        for dump_type in ["sms", "calls", "contacts"]:
            table_name = ''.join(c for c in dump_type if c.isalpha())
            dumps[table_name] = {}
            cur = conn.cursor()

            cur.execute(f"PRAGMA table_info({table_name});")
            table_info = cur.fetchall()
            dumps[table_name]['headers'] = [h[1] for h in table_info]

            cur.execute(f"SELECT * FROM {table_name};")
            dumps[table_name]['rows'] = cur.fetchall()
    # print(dumps)
    return render_template("dashboard.html.j2", dumps=dumps)


# don't put these into "ifmain"
scheduler.init_app(app)
scheduler.start()
scheduler.run_job('dump_update')


if __name__ == '__main__':
    app.run(debug=True)
