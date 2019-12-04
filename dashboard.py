#!/usr/bin/env python3
from flask import Flask, render_template, redirect, url_for

app = Flask(__name__, template_folder="")


class MetaDump:
    def __init__(self):
        # you will need to execute metasploit commands, get the dump files' names and put them below
        sms_path = "sms_dump.txt"
        calls_path = "calllog_dump.txt"
        contacts_path = "contacts_dump.txt"

        self.geo = None
        self.geo_wlan = None
        self.sms = self.parse_dump(sms_path, "sms")
        self.calls = self.parse_dump(calls_path, "calls")
        self.contacts = self.parse_dump(contacts_path, "contacts")

    def parse_dump(self, path, dump_type):
        meta = {'_name': dump_type.capitalize()}
        headers = ['ID']
        dump = {}
        try:
            with open(path, 'r', encoding='utf-8') as dump_f:
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
                            meta[key.strip()] = value.strip()
        except StopIteration:
            dump = {"headers": headers, "rows": [[idx] + list(row.values()) for idx, row in dump.items()]}
            return {"meta": meta, "dump": dump}

    @property
    def tables(self):
        return [self.sms, self.calls, self.contacts]


@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    dump = MetaDump()
    return render_template(
        "dashboard.html.j2",
        geo=dump.geo,
        geo_wlan=dump.geo_wlan,
        tables=dump.tables,
    )


if __name__ == '__main__':
    app.run(debug=True)
