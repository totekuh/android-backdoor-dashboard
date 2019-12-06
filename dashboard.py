#!/usr/bin/env python3
import sqlite3
from pathlib import Path

from flask import Flask, redirect, render_template, url_for
from flask_apscheduler import APScheduler


class Config(object):
    SCHEDULER_API_ENABLED = True
    DUMP_DIRECTORY_PATH = Path('/home/retr0/Desktop/dump')
    DB = "dump.db"


scheduler = APScheduler()
app = Flask(__name__, template_folder="")
app.config.from_object(Config())


def dump_parse_save_unique(requested_dumps):
    # insert meterpreter dump here
    # after the dumps are done, they will be picked up
    for dump_type in requested_dumps:
        meta = {
            'DumpType': dump_type
        }
        # headers = []
        dump = {}
        try:
            with open(app.config['DUMP_DIRECTORY_PATH'] / f"{dump_type}.txt", 'r', encoding='utf-8') as dump_f:
                idx = None
                while True:
                    line = next(dump_f).strip()
                    if line:
                        if line.startswith("#"):
                            idx = line
                            dump[idx] = {}
                        elif idx:
                            key, value = [s.strip() for s in line.split(":", maxsplit=1)]
                            dump[idx][key] = value
                            # if key not in headers:
                            #     headers.append(key)
                        elif ":" in line:
                            key, value = [s.strip() for s in line.split(":", maxsplit=1)]
                            meta[key] = value
        except StopIteration:
            dump = list(dump.values())
            with sqlite3.connect(app.config['DB']) as conn:
                for row in dump:
                    sql_insert(conn, dump_type, row)
        except FileNotFoundError:
            pass


def sanitize(query: str):
    return ''.join(c for c in query if c.isalnum())


def sql_insert(conn, table, row_dict):
    table = sanitize(table)
    headers = [sanitize(k).lower() for k in row_dict.keys()]
    data_placeholders = [f":{sanitize(k)}" for k in row_dict.keys()]
    conditions = " AND ".join(
                f"{header} ={data_placeholder}" for header, data_placeholder in zip(headers, data_placeholders))
    marked_up_query = f"INSERT INTO {table} " \
        f"({', '.join(headers)}) " \
        f"SELECT {', '.join(data_placeholders)} WHERE NOT EXISTS(SELECT 1 FROM {table} WHERE {conditions});"
    conn.execute(marked_up_query, row_dict)


def sql_load(requested_dumps):
    dumps = {}
    with sqlite3.connect(app.config['DB']) as conn:
        for dump_type in requested_dumps:
            table_name = ''.join(c for c in dump_type if c.isalpha())
            dumps[table_name] = {}
            cur = conn.cursor()

            cur.execute(f"PRAGMA table_info({table_name});")
            table_info = cur.fetchall()
            dumps[table_name]['headers'] = [h[1] for h in table_info]

            cur.execute(f"SELECT * FROM {table_name};")
            dumps[table_name]['rows'] = cur.fetchall()
    return dumps


@scheduler.task('interval', id='dump_update', seconds=10, misfire_grace_time=900)
def dump_update():
    with sqlite3.connect(app.config['DB']) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS sms (type TEXT, date TEXT, address TEXT, status TEXT, message TEXT);")
        conn.execute("CREATE TABLE IF NOT EXISTS calls (type TEXT, date TEXT, number TEXT, name TEXT, duration TEXT);")
        conn.execute("CREATE TABLE IF NOT EXISTS contacts (number TEXT, name TEXT);")

    dump_parse_save_unique(["sms", "calls", "contacts"])
    print('Dump!')


@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    dumps = sql_load(["sms", "calls", "contacts"])
    # print(dumps)
    return render_template("dashboard.html.j2", dumps=dumps)


# don't put these into "ifmain"

scheduler.init_app(app)
scheduler.start()
scheduler.run_job('dump_update')

if __name__ == '__main__':
    app.run(debug=True)
