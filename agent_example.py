#!/usr/bin/env python3

import agent
from pathlib import Path

agent.VERSION = 1

def echo(t: agent.Task):
    agent.writer_queue.put(f"{t.user}: {t.args}")

agent.commands.update({
    "echo": echo
})

if __name__ == "__main__":
    agent.main(
        server_host= "localhost",
        server_port = 8022,
        user = "example1",
        key = Path("../ex1"),
        known_hosts = Path("../known"))
