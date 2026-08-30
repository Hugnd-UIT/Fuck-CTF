import os
import time
import docker

def init(config):
	client = docker.from_env()

	path = os.path.join(os.getcwd(), 'workspace')
	if not os.path.exists(path):
		os.makedirs(path, exist_ok=True)
	found = client.containers.list(filters={'name': config["sandbox"]}, all=True)

	if found:
		container = found[0]
	else:
		print(f"[SANDBOX] Creating new {config['sandbox']} This will take a few minutes If you interrupt this process delete the {config['sandbox']} container and run the script again")
		
		# Config container
		image = client.images.pull('kalilinux/kali-rolling')
		container = client.containers.run(
			'kalilinux/kali-rolling',
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
		commands = (
			'apt update && '
			'apt -y install kali-linux-headless sshpass curl && '
			'ssh-keyscan -p 2220 bandit.labs.overthewire.org >> ~/.ssh/known_hosts && '
			'ssh-keyscan -p 2231 krypton.labs.overthewire.org >> ~/.ssh/known_hosts && '
			'ssh-keyscan -p 2223 leviathan.labs.overthewire.org >> ~/.ssh/known_hosts'
		)
		result = container.exec_run(f'/bin/bash -c "{commands}"', stdout=True, stderr=True)
		print('[SANDBOX]', result.output.decode()) 

		# Verify installation
		check = container.exec_run('which curl')
		if check.exit_code != 0:
			print("[SANDBOX] Failed to install curl Please check the logs")

		container.stop()
		print(f"[SANDBOX] The {config['sandbox']} has been set up")

	if container.status != 'running':
		container.start()

		# Start TUN if needed
		container.exec_run('/bin/bash -c "mkdir -p /dev/net && mknod /dev/net/tun c 10 200 && chmod 600 /dev/net/tun"')
		
		# Start VPN if provided
		if "vpn" in config and os.path.exists(f"{path}/{config['vpn']}"):
			container.exec_run(f'openvpn /data/{config["vpn"]}', detach=True)
		time.sleep(3)

	return container