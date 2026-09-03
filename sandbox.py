import os
import time
import docker
import cli.sandbox as sandbox_ui

def init(config):
	client = docker.from_env()

	path = os.path.join(os.getcwd(), 'workspace')
	if not os.path.exists(path):
		os.makedirs(path, exist_ok=True)
	found = client.containers.list(filters={'name': config["sandbox"]}, all=True)

	if found:
		container = found[0]
	else:
		start = time.time()
		sandbox_ui.create(config['sandbox'])
		
		# Check or build image
		image = config.get("image", "fuckctf:latest")
		try:
			client.images.get(image)
		except Exception:
			if os.path.exists("Dockerfile"):
				image = "fuckctf:latest"
				client.images.build(path=".", tag=image, rm=True)
			else:
				client.images.pull("kalilinux/kali-rolling")
				image = "kalilinux/kali-rolling"

		container = client.containers.run(
			image,
			detach=True,
			tty=True,
			name=config["sandbox"],
			volumes={path: {'bind': '/data', 'mode': 'rw'}},
			cap_add=['NET_ADMIN', 'SYS_PTRACE'],
			devices=["/dev/net/tun"],
			environment={"DEBIAN_FRONTEND": "noninteractive"},
			stdin_open=True
		)

		# Set up container
		if image == "kalilinux/kali-rolling":
			commands = (
				'apt update && '
				'apt -y install kali-linux-headless sshpass curl && '
				'ssh-keyscan -p 2220 bandit.labs.overthewire.org >> ~/.ssh/known_hosts && '
				'ssh-keyscan -p 2231 krypton.labs.overthewire.org >> ~/.ssh/known_hosts && '
				'ssh-keyscan -p 2223 leviathan.labs.overthewire.org >> ~/.ssh/known_hosts'
			)
			result = container.exec_run(f'/bin/bash -c "{commands}"', stdout=True, stderr=True)
			sandbox_ui.output(result.output.decode()) 

			check = container.exec_run('which curl')
			if check.exit_code != 0:
				sandbox_ui.curlerr()

		container.stop()
		sandbox_ui.success()

	if container.status != 'running':
		container.start()

		# Start TUN if needed
		container.exec_run('/bin/bash -c "mkdir -p /dev/net && mknod /dev/net/tun c 10 200 && chmod 600 /dev/net/tun"')
		
		# Start VPN if provided
		if "vpn" in config and os.path.exists(f"{path}/{config['vpn']}"):
			container.exec_run(f'openvpn /data/{config["vpn"]}', detach=True)
		time.sleep(3)

	return container