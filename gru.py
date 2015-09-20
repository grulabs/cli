#!/usr/bin/env python
import argparse
import json
import os
import requests
import signal
import sys

import termios, fcntl, sys, os
import requests

from socketIO_client import LoggingNamespace
from socketIO_client import SocketIO


BASE_SERVER_URL = "http://www.grulabs.co"
CONFIG_FILE_PATH = os.path.join(os.path.expanduser("~"), '.weconfig')

class APIError(Exception):
	pass

def create(name, image):
	data = read_config_data()

	if name in data:
		raise APIError("VM already exists.")

	r = requests.post("%s/create?image=%s" % (BASE_SERVER_URL, image))
	print("Created %s from image %s." % (name, image))

	with open (CONFIG_FILE_PATH, 'w+') as fh:
		data[name] = {'id': r.json()["id"]}
		jsdata = json.dumps(data)
		fh.write(jsdata)

def delete(name):
	data = read_config_data()

	if name not in data:
		raise APIError("VM does not exist.")
	r = requests.post("%s/delete?id=%s" % (BASE_SERVER_URL, data[name]["id"]))
	print("Removed %s." % (name))

	with open (CONFIG_FILE_PATH, 'w+') as fh:
		data.pop(name, None)
		jsdata = json.dumps(data)
		fh.write(jsdata)


def attach(name, cmd):
	data = read_config_data()
	if name not in data:
		raise APIError("VM does not exist.")

	params = {"taskId": data[name]["id"]}
	if cmd:
		params['cmd'] = cmd
	socketIO = SocketIO( BASE_SERVER_URL, 80, params=params)
	socketIO.on('data', on_proxy_response)


	def resizeHandler(signum, frame):
		print "resize-window signal caught"
		pass

	signal.signal(signal.SIGWINCH, resizeHandler)
	fd = sys.stdin.fileno()

	oldterm = termios.tcgetattr(fd)
	newattr = termios.tcgetattr(fd)
	newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
	termios.tcsetattr(fd, termios.TCSANOW, newattr)

	oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
	fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
	try:
		while True:
			socketIO.wait(seconds=0.001)
			try:
				c = sys.stdin.read(1)
				socketIO.emit("data", c)
			except IOError:
				pass
	except KeyboardInterrupt:
		print "\n\nExiting..."

	termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
	fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)

def on_proxy_response(*args):
	try:
		sys.stdout.write(args[0])
		sys.stdout.flush()
	except:
		pass

def read_config_data():
	data = {}
	if os.path.isfile(CONFIG_FILE_PATH):
		with open (CONFIG_FILE_PATH, 'r+') as fh:
			try:
				data = json.load(fh)
			except ValueError:
				data = {}
	return data

def write_config_data(data):
	with open (CONFIG_FILE_PATH, 'w+') as fh:
		jsdata = json.dumps(data)
		fh.write(jsdata)


def expose(name, ports):
	data = read_config_data()
	if name not in data:
		raise APIError("VM does not exist.")

	mapping = data[name]['ports'] if 'ports' in data[name] else {}
	for port in ports:
		r = requests.post("%s/port?port=%s&taskId=%s" % (BASE_SERVER_URL, port, data[name]["id"]))
		mapping[port] = r.json()['port']

	data[name]['ports'] = mapping
	write_config_data(data)

	print "Ports Exposed: %s" % (", ").join(ports)
	for port, mapped_port in mapping.iteritems():
		print "\t%s - %s:%s" % (port, BASE_SERVER_URL, mapped_port)

def status(name):
	print "Status: STARTED"
	data = read_config_data()
	if name not in data:
		raise APIError("VM does not exist.")

	if "ports" not in data[name]:
		print "No ports mapped."
	else:
		print "Ports:"
		for port, mapped_port in data[name]["ports"].iteritems():
			print "\t%s - %s:%s" % (port, BASE_SERVER_URL, mapped_port)

def list():
	vms = read_config_data().keys()
	if len(vms) > 0:
		for vm in vms:
			print vm
	else:
		print "No vms."
def parse_args():
	parser = argparse.ArgumentParser(description='Process some integers.')
	subparsers = parser.add_subparsers(dest="command")

	create_parser = subparsers.add_parser("create")
	create_parser.add_argument('--image', '-i', default='keshavdv/izanamee')
	create_parser.add_argument('name', metavar='NAME')

	delete_parser = subparsers.add_parser("delete", help='delete a vm')
	delete_parser.add_argument('name', metavar='NAME')

	exec_parser = subparsers.add_parser("exec", help='launch a shell')
	exec_parser.add_argument('--cmd', '-c')
	exec_parser.add_argument('name', metavar='NAME')

	list_parser = subparsers.add_parser("ls", help='list vms')

	status_parser = subparsers.add_parser("status", help='status of vm')
	status_parser.add_argument('name', metavar='NAME')

	expose_parser = subparsers.add_parser("expose", help='expose a port')
	expose_parser.add_argument('--port', '-p', action='append', required=True)
	expose_parser.add_argument('name', metavar='NAME')

	return parser.parse_args()


def main():
	args = parse_args()
	if args.command == "create":
		create(args.name, args.image)
	elif args.command == "delete":
		delete(args.name)
	elif args.command == "exec":
		attach(args.name, args.cmd)
	elif args.command == "expose":
		expose(args.name, args.port)
	elif args.command == "status":
		status(args.name)
	elif args.command == "ls":
		list()
	else:
		print "Command not recognized"
		sys.exit(1)

if __name__ == '__main__':
	main()