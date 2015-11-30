'''
Simple client that is able to issue bandwidth throttling requests
to other machines.
'''
import zmq
import argparse
import sys
import random
import numpy

'''
Actually sends a throttle request to the given destination, telling
it to limit bandwidth for a given IP to the given value.
'''
def send_throttle_request(destination, throttle_ip, bandwidth):
	print "Going to send throttle request to " + destination
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect("tcp://" + destination + ":" + args.port)
	socket.send("set " + throttle_ip + ":" + bandwidth)
	message = socket.recv()
	print "Received reply ",message

'''
Actually sends a throttle request to the given destination, telling
it to limit bandwidth for its default interface. 
'''
def send_throttle_interface_request(destination, bandwidth):
	print "Going to send throttle interface request to " + destination
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect("tcp://" + destination + ":" + args.port)
	socket.send("set-all " + bandwidth)
	message = socket.recv()
	print "Received reply ",message

'''
Send a reset request to the given destination, telling it to remove
any bandwidth restrictions in place.
'''
def send_reset_request(destination):
	print "Going to send reset request to " + destination
	context = zmq.Context()
	socket = context.socket(zmq.REQ)
	socket.connect("tcp://" + destination + ":" + args.port)
	socket.send("reset")
	message = socket.recv()
	print "Received reply ",message
	

# We either want an individual command or a file that contains commands.
parser = argparse.ArgumentParser()
set_group = parser.add_mutually_exclusive_group(required = True)
set_group.add_argument("--set", help = "throttle the bandwidth between machines: <ip1>:<ip2>:<bandwidth>")
set_group.add_argument("--set-all", help = "throttle the bandwidth of an interface on the given machines: <ip>:<bandwidth>")
set_group.add_argument("--reset", help = "removes the bandwidth throttles on the given machines: <ip1>:<ip2>:..")
set_group.add_argument("--set-file", help = "the given file specifies the bandwidth between machines. See --set for the correct syntax")
set_group.add_argument("--generate-uniform", help = """
takes as first input concatenated ip addresses (<ip1>:<ip2>..), as second input concatenated bandwidth values
(<bw1>:<bw2>..) and as third input a file. It uniformly distributes the possible bandwidth values over the links. This generates an output
file which can be given to the program again using --set-file""")
set_group.add_argument("--generate-9-triangle", help = """
takes as first input concatenated ip addresses (<ip1>:<ip2>..), as second input concatenated bandwidth values
(<bw1>:<bw2>..) and as third input a file. There have to be 9 ip addresses and 3 bandwidth values. It will
generate a 3-triangle topology where vertices in the same triangle have the fastest link value, vertices
in different triangles have a lower bandwidth value and vertices 'separated' by a triangle have the
lowest bandwidth value. The file can be given to the program again using --set-file""")
parser.add_argument("--port", help = "The port on the server that the client connects to")
args = parser.parse_args()

# Limit a single link.
if args.set:
	parts = args.set.split(":")
	if len(parts) < 3 or not args.port:
		parser.print_usage()
		sys.exit()

	# Both ends need traffic shaping.
	send_throttle_request(parts[0], parts[1], parts[2])
	send_throttle_request(parts[1], parts[0], parts[2])

# Limit an interface.
if args.set_all:
	parts = args.set_all.split(":")
	if len(parts) < 2 or not args.port:
		parser.print_usage()
		sys.exit()

	# Send the request.
	send_throttle_interface_request(parts[0], parts[1]):

# Limit one or multiple links in the given file.
elif args.set_file:
	f = open(args.set_file, "r")
	for line in f:
		parts = line.split(":")
		if len(parts) < 3 or not args.port:
			print("Invalid line, skipping request: " + line)
		else:
			# Both ends need traffic shaping.
			send_throttle_request(parts[0], parts[1], parts[2])
			send_throttle_request(parts[1], parts[0], parts[2])
	f.close()

# Uniformly distribute available bandwidth values between links.
elif args.generate_uniform:
	parts = args.generate_uniform.split(" ")
	if (len(parts) < 3):
		parser.print_usage()
		sys.exit()
	ips = parts[0].split(":")
	bandwidth_values = parts[1].split(":")
	output_file = parts[2]

	# First generate all relevant link pairs.
	link_pairs = []
	remaining_ips = list(ips)
	for from_ip in ips:
		remaining_ips.remove(from_ip)
		for to_ip in remaining_ips:
			link_pairs.append((from_ip, to_ip))

	# Now create a list that holds just as much entries,
	# but with bandwidth values. Will randomly select from that.
	possible_bandwidth_values = []
	for i in range(0, len(link_pairs)):
		possible_bandwidth_values.append(bandwidth_values[i % len(bandwidth_values)])

	# Now randomly assign a bandwidth value to a link pair and
	# write that to the output file.
	f = open(output_file, "w")
	for pair in link_pairs:
		choice = random.choice(possible_bandwidth_values)
		from_ip, to_ip = pair
		f.write(from_ip + ":" + to_ip + ":" + choice + "\n")
		possible_bandwidth_values.remove(choice)	
	f.close()

# Generate the 9 triangle topology.
elif args.generate_9_triangle:
	parts = args.generate_9_triangle.split(" ")
	if (len(parts) < 3):
		parser.print_usage()
		sys.exit()
	ips = parts[0].split(":")
	bandwidth_values = parts[1].split(":")
	output_file = parts[2]
	if len(ips) != 9:
		print("Expects 9 IP addresses")
		sys.exit()
	if len(bandwidth_values) != 3:
		print("Expects 3 bandwidth values in descending order of size")
		sys.exit()

	# Will hold all link pairs.
	link_pairs = []

	# First generate all triangle link pairs.
	triangles = numpy.split(numpy.array(ips), 3)
	for triangle in triangles:
		remaining = numpy.copy(triangle)
		remaining = remaining.tolist()
		for from_ip in triangle:
			remaining.remove(from_ip)
			for to_ip in remaining:
				link_pairs.append((from_ip, to_ip, bandwidth_values[0]))

	# Now generate the link pairs between subsequent triangles.
	for index in range(2):
		triangle_from = triangles[index]
		triangle_to = triangles[index + 1]
		for from_ip in triangle_from:
			for to_ip in triangle_to:
				link_pairs.append((from_ip, to_ip, bandwidth_values[1]))

	# Now generate the link pairs between triangles separated by a triangle.
	for from_ip in triangles[0]:
		for to_ip in triangles[2]:
			link_pairs.append((from_ip, to_ip, bandwidth_values[2]))
	
	# Now generate the output bandwidth.			 
	f = open(output_file, "w")
	for pair in link_pairs:
		from_ip, to_ip, value = pair
		f.write(from_ip + ":" + to_ip + ":" + value + "\n")
	f.close()

# Reset throttles on the given machines.
elif args.reset:
	parts = args.reset.split(":")
	for ip in parts:
		send_reset_request(ip)
