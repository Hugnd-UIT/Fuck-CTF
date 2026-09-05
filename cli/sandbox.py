from .core import node, line

# Log container creation
def create(name):
    node("Sandbox", "45.2s", "blue")
    line(f"Creating new {name} This will take a few minutes If you interrupt\nthis process delete the {name} container and run the script again")

# Log creation success
def success():
    line("Success!")

# Log missing curl
def curlerr():
    line("Failed to install curl please check the logs")

# Log container output
def output(out):
    line(out)