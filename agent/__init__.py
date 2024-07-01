# Copyright (c) 2024 Julian Müller (ChaoticByte)
# License: MIT

from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from datetime import datetime as _datetime
from pathlib import Path as _Path
from queue import Empty as _Empty
from queue import Queue as _Queue
from sys import stderr as _stderr
from time import time as _time
from typing import IO as _IO

from paramiko import SSHClient


VERSION = "unknown"
BASE_VERSION = 1
TIME_A = _time()


# helpers & types

def log(*args):
    print(_datetime.now().isoformat(), *args, file=_stderr)


class Task:
    def __init__(self, user: str, command: str, args: str):
        assert type(user) == str
        assert type(command) == str
        assert type(args) == str
        self.user = user
        self.command = command
        self.args = args


# commands

def command_hi(task: Task):
    writer_queue.put(f"Hi {task.user}! Running agent v{BASE_VERSION}:{VERSION} since {(_time()-TIME_A):.2f} seconds.")

def command_help(task: Task):
    writer_queue.put(f"Available commands: {', '.join(commands)}")

commands = {
    "hi": command_hi,
    "help": command_help
}


# internal

_stop = False
_worker_queue = _Queue()
writer_queue = _Queue()

def _ssh_listener(stdout: _IO):
    global _stop
    log("Starting SSH Listener")
    while not _stop:
        try:
            if stdout.channel.closed:
                log("Connection lost.")
                break
            # parse message
            l = stdout.readline().strip("\n ")
            if l == "": continue
            if not ": " in l: continue
            username, rest = l.split(": ", 1)
            if " " in rest:
                command, args = rest.split(" ", 1)
            else:
                command, args = rest, ""
            # put in queue
            _worker_queue.put(Task(username, command, args))
        except Exception as e:
            log(f"An exception occured: {e.__class__.__name__} {e}")
    _stop = True
    log("Stopping SSH Listener")

def _ssh_writer(stdin: _IO):
    global _stop
    log("Starting SSH Writer")
    while not _stop:
        try:
            l = writer_queue.get(timeout=1)
            if type(l) == str:
                stdin.write(l.rstrip("\n") + "\n")
        except _Empty:
            pass
    log("Stopping SSH Writer")

def _worker():
    global _stop
    log("Starting SSH Worker")
    while not _stop:
        try:
            t = _worker_queue.get(timeout=1)
            if t.command in commands:
                commands[t.command](t)
        except _Empty:
            pass
        except KeyboardInterrupt:
            log("Keyboard Interrupt")
            _stop = True
    log("Stopping Worker")

def main(server_host: str, server_port: int, user: str, key: _Path, known_hosts: _Path):
    # check config
    assert type(server_host) == str
    assert type(server_port) == int
    assert type(user) == str
    assert isinstance(key, _Path)
    assert key.exists()
    assert isinstance(known_hosts, _Path)
    assert known_hosts.exists()
    # start client
    client = SSHClient()
    stdin, stdout, stderr = None, None, None
    tpe = _ThreadPoolExecutor()
    try:
        client.get_host_keys().clear()
        client.load_host_keys(str(known_hosts.resolve()))
        client.connect(hostname=server_host, port=server_port, username=user, key_filename=str(key.resolve()))
        stdin, stdout, stderr = client.exec_command("", get_pty=False)
        tpe.submit(_ssh_listener, stdout)
        tpe.submit(_ssh_writer, stdin)
        _worker()
    except Exception as e:
        log(f"An exception occured: {e.__class__.__name__} {e}")
        stop = True
    finally:
        client.close()
        if stdin is not None:
            stdin.close()
            stdin.channel.shutdown_write() # shutdown channel
        if stdout is not None: stdout.close()
        if stderr is not None: stderr.close()
        tpe.shutdown() # shutdown thread pool
