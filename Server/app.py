from __future__ import print_function
import time
import urllib
from random import randint
import paho.mqtt.client as paho
import Telstra_Messaging
from Telstra_Messaging.rest import ApiException
from flask import Flask, abort, request, render_template
from tinydb import TinyDB, Query
from tinydb.operations import delete, add

app = Flask(__name__)

db = TinyDB('../db.json')

client_id = ''
client_secret = ''
grant_type = ''

# default number length, this can be overridden by the admin user game on 
nlen = 6

# default number of tries a user can do before needing to see an admin user 
maxTries = 3

#admin mobiles 
adminlist = ['+61400000000']

#callbackurl
cback = "https://smsafe.telstradev.com"

def broker(msg):
	client= paho.Client("telstradev") 
	client.connect("telstradev.com", 7337)
	client.publish("smsafe",msg)
	client.disconnect()

def provision():
	api_instance = Telstra_Messaging.AuthenticationApi()
	
	api_response = api_instance.auth_token(client_id, client_secret, grant_type)

	configuration = Telstra_Messaging.Configuration()
	configuration.access_token = api_response.access_token

	api_instance = Telstra_Messaging.ProvisioningApi(Telstra_Messaging.ApiClient(configuration))
	body = Telstra_Messaging.ProvisionNumberRequest(30, cback)

	api_response = api_instance.create_subscription(body)
	return api_response.destination_address

def sendsms(to, msg):
    api_instance = Telstra_Messaging.AuthenticationApi()

    api_response = api_instance.auth_token(client_id, client_secret, grant_type)

    configuration = Telstra_Messaging.Configuration()
    configuration.access_token = api_response.access_token

    api_instance = Telstra_Messaging.MessagingApi(Telstra_Messaging.ApiClient(configuration))
    var = {'to': to, 'body': msg}

    api_response = api_instance.send_sms(var)

def ran(nlen):
	return ''.join(["%s" % randint(0, 9) for num in range(0, nlen)])

def optOut(mob):
	# single opt out of getting messages
	print(mob+" opted out")

#do safe interaction things here
def safeComm(comm):

	if comm == "open" or comm == "prize":
		#check if admin or winner
		smsAdmin("The IOT MASTERMIND safe is opening, Please place trays in upright position and remember to *PICKLE RICKKKKK*.")
		broker("open")

	elif comm == "close": 
		#check if admin
		smsAdmin("The IOT MASTERMIND safe is closing, please stand clear of the door and keep all fingers inside the ride at all times.")
		broker("close")

#start a new game
def imGame(comm, mob, nlen):
	#todo: msg the user base when a new game starts or one ends 
	#todo: msg the admins to let them know a new game has started
	g = Query()

	game = db.get((g.status == 0) & (g.num.exists()))

	if comm == "start":
		# check to see if theres already a game running
		if game:
			sendsms(mob, "Theres a game already running")
		else:
			v = ran(nlen)
			
			smsAdmin("Game on!")

			db.insert({'num': v, 'status': 0, 'plays': 0, 'winner': '', 'claimed': 0})

			#reset everyones tries counter
			db.update({'tries': 0}, (g.phone.exists()) & (g.terms == 1) & (g.status == 0))
			
			spamEveryone("A new game of IOT MASTERMIND has started. The new number to guess has "+str(nlen)+" digits. SMS back a number containing 0-9 to get started.\n\nYou get 3 tries at this round, drop by the Telstra booth to chat to one of the staff if you need more.")

	elif comm == "stop":
		if game:
			db.update({'status': 1}, doc_ids=[game.doc_id])			
			sendsms(mob, "The game has been stopped")
			# didnt put this on because i thought if the game is stopped the message should come from an admin as to why
			# spamEveryone("The current IOT MASTERMIND game has been stopped")
		else:
			sendsms(mob, "There is no game running at the moment")
	elif comm == "status":
		if game:
			sendsms(mob, "The game running at the moment has had "+str(game['plays'])+" guesses, the number to guess is "+game['num'])				
		else: 
			sendsms(mob, "There is no game running at the moment")
	else: 
		print("imGame error") 



#spam everyone a message
def spamEveryone(msg):

	t = Query()

	loop = db.search((t.optout == 0) & (t.terms == 1) & (t.status == 0))

	for i in loop:
		sendsms(i['phone'], msg)

def smsAdmin(msg):

	t = Query()

	loop = db.search(t.admin == 1)

	for i in loop:
		sendsms(i['phone'], "Admin: "+ msg)	


#creates a new user
def newuser(f):

	#todo: status 1 means the user has already won
	#todo: status 2 means the user has claimed the prize
	db.insert({'phone': f, 'optout': 0, 'tries': 0, 'status': 0, 'terms': 0, 'admin': 0})

def ncheck (o,g):

	o = [int(x) for x in str(o)]
	g = [int(x) for x in str(g)]

	output = dict()
	output['done'] = 0
	output['guess'] = "Guess : ["
	output['match'] = "Result: ["

	for index, item in enumerate(g):
		
		output['guess'] += str(item)

		if item == o[index]:
			output['match'] += (u'\u2713')
		else:
			# if o.__contains__(item) and o.count(item) >= g.count(item):
			# 	output['match'] += "-"
			# else:
			output['match'] += "X"

		if index < int(len(o)-1):
			output['guess'] += " | "
			output['match'] += " | "
		else: 
			break

	# check to see if the 2 numbers match
	if(output['match'].count(u'\u2713')==len(o)):
		output['done'] = 1


	output['guess'] += "]"
	output['match'] += "]"

	return output

@app.route("/")
def home():
	return "hello world, this probably isnt the page you are looking for"

@app.route("/provision")
def prov():
	
	p = provision()
	return "SMS your guess to the following number: " + p

@app.route("/", methods=['POST'])
def post():

	data = request.get_json()

	q = Query()

	game = db.get((q.status == 0) & (q.num.exists()))

	if data['from']:
		user = db.get(q.phone == data['from'])

		#if the user mobile doesnt exist in the db or user wants instructions
		if user is None or data['body'].lower() == "start": 
			if user is None: newuser(data['from'])

			#reload user data
			user = db.get(q.phone == data['from'])

			sendsms(data['from'], "IOT MASTERMIND \n\nGuess the number to unlock the Arduino safe and win a brand new Arduino MKR NB 1500.")


		#check for master admin and update in db (usually first time run but if someone deletes it will update)
		if adminlist.__contains__(data['from']) and user['admin']==0:
			user['admin'] = 1
			db.update({'admin': 1}, q.phone == data['from'])

		#do admin things in here if the user is listed as an admin
		if user['admin'] == 1: 

			#split the sms body down by spaces (dont put too many spaces or this wont work)
			first = data['body'].split(' ')

			#admin functions 
			if first[0].lower() == "admin":

				#add admin user
				if first[1].lower() == "add" or first[1].lower() == "delete":

					# clean up the sent mobile number
					mob = "+61" + str(first[2][1:10]) if str(first[2][0]) == "0" else str(first[2])

					if first[1].lower() == "add": 
						db.update({'admin': 1}, q.phone == mob)
						sendsms(mob, "You have been promoted to admin in the IOT Mastermind game")
						sendsms(data['from'], mob+" has been promoted to admin")
					elif first[1].lower() == "delete":
						db.update({'admin': 0}, q.phone == mob)
						sendsms(data['from'], mob+" has been removed as an admin")
				# start or stop game
				elif first[1].lower() == "open" or first[1].lower() == "close":

					safeComm(first[1].lower())

				elif first[1].lower() == "guesses" or first[1].lower() == "tries":
					
					# clean up the sent mobile number
					mob = "+61" + str(first[2][1:10]) if str(first[2][0]) == "0" else str(first[2])
					
					db.update({'tries': -1}, q.phone == mob)
					sendsms(mob, "You have been given unlimited guesses in this round of the IOT Mastermind game")
					sendsms(data['from'], mob+" has been given unlimited guesses in this round of the IOT Mastermind game")

				elif first[1].lower() == "start" or first[1].lower() == "stop" or first[1].lower() == "status":

					# check for a digit in the message or use the default one, probs could have done this bit better but *shrugs*
					try:
						numLen=first[2] if first[2].isdigit() else nlen
					except IndexError:
						numLen=nlen

					imGame(first[1].lower(), data['from'], int(numLen))

				elif first[1].lower() == "msg":
					msg = data['body'].split("msg ")
					spamEveryone(msg[1])

		# check user terms and conditions accept
		if user['terms'] == 0:

			tmsg = ""

			if data['body'].lower() == "y": 
				db.update({'terms': 1}, q.phone == data['from'])
				w = "Terms and conditions accepted, you are ready to play.\n\n"

				# send message back if theres a game running or not
				tmsg = w+"I am thinking of a number which has "+str(len(game['num']))+" digits. SMS back a number containing 0-9 to get started.\n\n To opt out at any time SMS back opt out." if game else w+"Theres no game running at the moment but keep an eye on your phone, we will message you as soon as it starts!"
				print(tmsg)
			else:
				tmsg = "Accept the terms and conditions to start playing https://bit.ly/2VxBlUY. SMS back Y or N to continue"

			sendsms(data['from'], tmsg)

		#do number processing things
		elif data['body'].isdigit() and user['optout'] == 0 and user['status'] < 1:
			#yep its a number alright and the user hasnt opted out yet or won a game already

			if game:

				if user['tries'] >= maxTries: 
					sendsms(data['from'], "Sorry it looks like you are out of guesses for this game, visit the Telstra booth and chat to one of the staff to get more.")
				else:
					x = ncheck(game['num'], data['body'])

					msg = x['guess'] + "\n" + x['match']  

					# update the game counter
					db.update(add('plays', 1), doc_ids=[game.doc_id])

					# user tries counter updates only if its not -1 (unlimited)
					if user['tries'] != -1: db.update(add('tries', 1), q.phone == data['from'])

					# if the 2 numbers match
					if x['done'] == 1:

						# update the open game db entry
						db.update({'status': 1, 'winner': data['from']}, doc_ids=[game.doc_id])

						#update the users db entry, mark as a winner and lock from further attempts
						db.update(add('status', 1), q.phone == data['from'])

						sendsms(data['from'], "Congratuations you got the code! \n\n" + msg + "\n\nHead on over to the Telstra booth to collect your prize.\nSMS back 'prize' when you are ready to unlock the safe.")

						# end the game
						smsAdmin("Someone has won the current IOT MASTERMIND game which was solved in "+str(game['plays']+1)+"!\n\nThe winning mobile number is "+data['from'])

						# end the game
						spamEveryone("Stop the presses, this round of IOT MASTERMIND has been won.\n\nStay tuned for the next round!")

						#todo: build the winning user unlock the safe function 

					else:
						sendsms(data['from'], "IOT MASTERMIND \n\n" + msg)

			else:
				sendsms(data['from'], "Theres no game running at the moment but keep an eye on your phone, we will message you as soon as it starts!\n\nWhile you wait why not register at https://dev.telstra.com and check out our API's.")


		elif data['body'].lower().find("opt") >= 0: 
			#opt out the user out or in
			msg = ""

			if data['body'].lower().find("out") >= 0:
				db.update({'optout': 1}, q.phone == data['from'])
				msg = "You have opted out of any more SMS from the IOT MASTERMIND game.\n\n To opt back in sms opt in"
			elif data['body'].lower().find("in") >= 0:
				db.update({'optout': 0}, q.phone == data['from'])
				msg = "You have opted back in for the IOT MASTERMIND game."
				#todo: add in new game deets in here 
			else:
				msg = "opt error"
			
			sendsms(data['from'], msg)
		elif user['status'] == 2 and user['admin'] == 0:
			#if the user has already won
			sendsms(data['from'], "It looks like you have already won a round of IOT MASTERMIND, remember to register at https://dev.telstra.com to get access to our IOT API's and more!")
			
		elif data['body'].lower() == "prize" and user['status'] == 1:
			#if the user is a winner and messages back prize to open the safe

			safeComm("open")

			sendsms(data['from'], "Congratulations on guessing the IOT MASTERMIND CODE\n\nPlease stand clear.... the IOT MASTERMIND safe is opening!")

			#mark the users record as done and dusted
			db.update({'status': 2}, q.phone == data['from'])

		else:
			if data['body'].lower() != "start" and user['admin'] == 0: 
				sendsms(data['from'], "Numbers only please")

	return ""

if __name__ == "__main__":
    app.run()

