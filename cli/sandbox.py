from .core import node, line

def create(name):
    node("Sandbox", "45.2s", "blue")
    line(f"Creating new {name} This will take a few minutes If you interrupt\nthis process delete the {name} container and run the script again")

def success():
    line("Success!")

def curlerr():
    line("Failed to install curl please check the logs")

def output(out):
    line(out)
