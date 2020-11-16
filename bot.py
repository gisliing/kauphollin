# bot.py

import os
import sqlite3
import discord
from dotenv import load_dotenv
import unidecode
import locale
import investpy
import math
import requests
import datetime

locale.setlocale(locale.LC_ALL, '')

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents().all()
client = discord.Client(intents=intents)

conn = sqlite3.connect('kaupholl.db')
c = conn.cursor()

stocks = ['HAGA', 'ICEAIR', 'MARL', 'ORIGO', 'EIMS',
		  'REGINN', 'VISS', 'SYN', 'TMGN', 'BRIMH',
		  'FESTI', 'SJOVA', 'EIKF', 'REITIR', 'SIMINN',
		  'ICESEA', 'SKEL', 'KVIKA', 'ARION']

funds = ['OIEFX', 'VFIAX']

forex = ['USD', 'EUR', 'BTC']

stock_commission = 0.01
fund_commission = 0.015

embed = None

def create_account(guild_id, author_id):
	c.execute('''SELECT *
				 FROM ASSETS
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?;''', [guild_id, author_id])
	rows = c.fetchall()
	if len(rows) == 0:
		c.execute('''INSERT INTO ASSETS(GUILD_ID, USER_ID, TYPE, TICKER, VOLUME) 
					 VALUES (?, ?, 'Deposit', 'DEBET', 1000000);''', [guild_id, author_id])
		for stock in stocks:
			c.execute('''INSERT INTO ASSETS(GUILD_ID, USER_ID, TYPE, TICKER, VOLUME) 
						 VALUES (?, ?, 'Stock', ?, 0);''', [guild_id, author_id, stock])
		for fund in funds:
			c.execute('''INSERT INTO ASSETS(GUILD_ID, USER_ID, TYPE, TICKER, VOLUME) 
						 VALUES (?, ?, 'Fund', ?, 0);''', [guild_id, author_id, fund])
		for fx in forex:
			c.execute('''INSERT INTO ASSETS(GUILD_ID, USER_ID, TYPE, TICKER, VOLUME) 
						 VALUES (?, ?, 'Currency', ?, 0);''', [guild_id, author_id, fx])
		conn.commit()
		return True
	return False

def get_scores(guild_id):
	c.execute('''SELECT DISTINCT USER_ID
				 FROM ASSETS
				 WHERE GUILD_ID = ?;''', [guild_id])
	user_ids = c.fetchall()
	scores = []
	for user_id in user_ids:
		print(user_id[0])
		c.execute('''SELECT TYPE, TICKER, VOLUME
					 FROM ASSETS
					 WHERE GUILD_ID = ?
					 AND USER_ID = ?
					 AND VOLUME <> 0;''', [guild_id, user_id[0]])
		rows = c.fetchall()
		score = 0
		for asset_type, ticker, volume in rows:
			if asset_type == 'Currency':
				score = score + volume*get_currency_price(ticker)
			elif asset_type == 'Stock':
				score = score + volume*get_stock_price(ticker)
			elif asset_type == 'Fund':
				score = score + volume*get_fund_price(ticker)
			else:
				score = score + volume
		scores.append([user_id[0], score])
		scores.sort(key = lambda x: x[1], reverse=True)
	return scores

def get_assets_info(guild_id, author_id):
	c.execute('''SELECT TYPE, TICKER, VOLUME
				 FROM ASSETS
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND VOLUME <> 0;''', [guild_id, author_id])
	rows = c.fetchall()
	if len(rows) == 0:
		return []
	return rows

def get_stock_info(ticker):
	info = investpy.get_stock_company_profile(stock=ticker, country='iceland')
	description = info["desc"]
	url = info["url"]
	price_now = get_stock_price(ticker)
	now = datetime.datetime.now()
	price_year_ago = investpy.get_stock_historical_data(stock=ticker,country='iceland',from_date=(now - datetime.timedelta(days=365)).strftime('%d/%m/%Y'),to_date=(now - datetime.timedelta(days=350)).strftime('%d/%m/%Y'))['Close'][-1]
	return price_now, price_year_ago, description, url

def get_fund_info(ticker):
	price_now = get_fund_price(ticker)
	now = datetime.datetime.now()
	price_year_ago = investpy.get_fund_historical_data(fund=get_fund_from_ticker(ticker), country='united states', from_date=(now - datetime.timedelta(days=365)).strftime('%d/%m/%Y'), to_date=(now - datetime.timedelta(days=350)).strftime('%d/%m/%Y'))['Close'][-1]*get_currency_price('USD')
	return price_now, price_year_ago

def get_currency_info(ticker):
	price_now = get_currency_price(ticker)
	now = datetime.datetime.now()
	if ticker in ["EUR", "USD"]:
		price_year_ago = investpy.get_currency_cross_historical_data(currency_cross="{}/ISK".format(ticker), from_date=(now - datetime.timedelta(days=365)).strftime('%d/%m/%Y'), to_date=(now - datetime.timedelta(days=350)).strftime('%d/%m/%Y'))['Close'][-1]
	else:
		price_year_ago = investpy.get_crypto_historical_data(crypto="bitcoin", from_date=(now - datetime.timedelta(days=365)).strftime('%d/%m/%Y'), to_date=(now - datetime.timedelta(days=350)).strftime('%d/%m/%Y'))['Close'][-1]*get_currency_price("USD")
	return price_now, price_year_ago

def get_stock_price(ticker):
	return investpy.get_stock_recent_data(stock=ticker, country='iceland', as_json=False, order='ascending')['Close'][-1]

def get_fund_price(ticker):
	return investpy.get_fund_recent_data(fund=get_fund_from_ticker(ticker), country='united states')['Close'][-1]*get_currency_price('USD')

def get_currency_price(ticker):
	if ticker in ["EUR", "USD"]:
		return investpy.get_currency_cross_recent_data(currency_cross='{}/ISK'.format(ticker))['Close'][-1]
	elif ticker in ["BTC"]:
		from_date = datetime.datetime.now().strftime("%d/%m/%Y")
		to_date = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%d/%m/%Y")
		btc_usd_rate = investpy.get_crypto_historical_data(crypto='bitcoin', from_date=from_date, to_date=to_date)['Close'][-1]
		return get_currency_price("USD") * btc_usd_rate

def get_price_by_type(asset_type, ticker):
	if asset_type == "Stock":
		return get_stock_price(ticker)
	elif asset_type == "Currency":
		return get_currency_price(ticker)
	elif asset_type == "Fund":
		return get_fund_price(ticker)
	elif asset_type == "Deposit":
		return 1
	else:
		return None

def get_debet_status(guild_id, author_id):
	c.execute('''SELECT VOLUME
				 FROM ASSETS
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND TICKER = "DEBET";''', [guild_id, author_id])
	rows = c.fetchall()
	return rows[0][0]

def get_security_status(guild_id, author_id, ticker):
	c.execute('''SELECT VOLUME
				 FROM ASSETS
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND TICKER = ?;''', [guild_id, author_id, ticker])
	rows = c.fetchall()
	return rows[0][0]

def make_purchase_transaction(guild_id, author_id, security, ticker, volume, amount):
	c.execute('''UPDATE ASSETS
				 SET VOLUME = VOLUME - ?
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND TICKER = "DEBET";''', [amount, guild_id, author_id])
	c.execute('''UPDATE ASSETS
				 SET VOLUME = VOLUME + ?
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND TICKER = ?;''', [volume, guild_id, author_id, ticker])
	conn.commit()
	return

def make_sale_transaction(guild_id, author_id, security, ticker, volume, amount):
	c.execute('''UPDATE ASSETS
				 SET VOLUME = VOLUME - ?
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND TICKER = ?;''', [volume, guild_id, author_id, ticker])
	c.execute('''UPDATE ASSETS
				 SET VOLUME = VOLUME + ?
				 WHERE GUILD_ID = ?
				 AND USER_ID = ?
				 AND TICKER = "DEBET";''', [amount, guild_id, author_id])
	conn.commit()
	return

def truncate(n, decimals=0):
	multiplier = 10 ** decimals
	return int(n * multiplier) / multiplier

def get_fund_from_ticker(ticker):
	if ticker == "OIEFX":
		return "Jpmorgan Equity Income Fund Class R2"
	elif ticker == "VFIAX":
		return "Vanguard 500 Index Fund Admiral Shares"
	else:
		return None

@client.event
async def on_ready():
	print(f'{client.user.name} has connected to Discord!')
	await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$hjálp"))

@client.event
async def on_message(message):
	if message.author == client.user:
		return

	msg = unidecode.unidecode(message.content).upper()

	embed = discord.Embed(title=client.user.name, color=0x0061ff)
	embed.set_thumbnail(url=client.user.avatar_url)
	embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
	embed.set_footer(text="Made by Gilli")

	if msg == '$HJALP':
		embed.add_field(name="Leiðbeiningar", value="Í Kauphöllinni geturðu keypt hlutabréf, gjaldeyri og hlutdeildarskírteini í sjóðum.", inline=False)
		embed.add_field(name="$stofna", value="'Til þess að stofna vörslureikning og byrja í viðskiptum.", inline=False)
		embed.add_field(name="$innlán", value="'Til þess að sjá eiginleika innlána.", inline=False)
		embed.add_field(name="$hlutabréf", value="'Til þess að sjá lista yfir hlutabréf og eiginleika.", inline=False)
		embed.add_field(name="$gjaldeyrir", value="'Til þess að sjá lista yfir gjaldeyri og eiginleika.", inline=False)
		embed.add_field(name="$sjóðir", value="'Til þess að sjá lista yfir sjóði og eiginleika.", inline=False)
		embed.add_field(name="$eignir", value="'Til þess að sjá lista yfir þínar eignir.", inline=False)
		embed.add_field(name="$eignir <tag>", value="' T.d. $eignir @ABC til þess að sjá lista yfir eignir annarra.", inline=False)
		embed.add_field(name="$stigatafla", value="'Til þess að sjá hvernig þú stendur miðað við aðra.", inline=False)
		embed.add_field(name="$<merki>", value="'T.d. '$ICEAIR' til þess að sjá meira um ákveðið verðbréf eða gjaldeyri.", inline=False)
		embed.add_field(name="$kaupa <merki> <upphæð>", value="T.d. $kaupa ICEAIR 100000 til þess að kaupa ákveðið verðbréf eða gjaldeyri fyrir ákveðna upphæð. Þegar þú kaupir verðbréf eða gjaldeyri verður þú að eiga næga innistæðu inni á DEBET-reikningi þínum.", inline=False)
		embed.add_field(name="$selja <merki> <upphæð>", value="T.d. $selja ICEAIR 100000 til þess að selja ákveðið verðbréf eða gjaldeyri fyrir ákveða upphæð. Þegar þú selur verðbréf eða gjaldeyri fer upphæðin sjálfkrafa inn á DEBET-reikninginn þinn.", inline=False)
		await message.channel.send(embed=embed)
		return

	if msg == '$STOFNA':
		res = create_account(message.guild.id, message.author.id)
		if res is True:
			embed.add_field(name="Vertu velkomin(n) í viðskipti.", value="Stofnaður hefur verið vörslureikningur í þínu nafni. Sláðu inn '$eignir' til að skoða þínar eignir eða '$hjálp' fyrir aðstoð.", inline=False)
			await message.channel.send(embed=embed)
			return
		embed.add_field(name="Þú hefur þegar stofnað vörslureikning.", value="Sláðu inn '$eignir' til að skoða þínar eignir eða '$hjálp' fyrir aðstoð.", inline=False)
		await message.channel.send(embed=embed)
		return

	if msg == '$INNLAN':
		embed.add_field(name="Eiginleikar:", value="Innlán (DEBET) er hefðbundinn bankareikningur sem þú notar til þess að kaupa verðbréf og gjaldmiðla og fá lagt inn á þig við sölu. Innlán bera 2.5% vexti á ársgrundvelli, greiddir út daglega í hádeginu.", inline=False)
		await message.channel.send(embed=embed)
		return

	if msg == '$HLUTABREF':
		embed.add_field(name="Hlutabréf:", value=", ".join(stocks), inline=False)
		embed.add_field(name="Eiginleikar:", value="Hlutabréf eru ávísun á ákveðinn eignarhlut í hlutafélagi. Tekið er gjald á viðskiptum með hlutabréf, 1%. Hlutabréf gefa af sér arð sem getur verið mjög mismunandi eftir dögum og leggst hann sjálfkrafa inn á DEBET-reikninginn þinn daglega.", inline=False)
		embed.add_field(name="Meiri upplýsingar:", value="Skráðu inn $<merki>, t.d. $ICEAIR fyrir frekari upplýsingar um einstök hlutabréf. Skráðu inn $kaupa <merki> <upphæð> eða $selja <merki> <upphæð> fyrir kaup eða sölu á hlutabréfi.", inline=False)
		await message.channel.send(embed=embed)
		return

	if msg == '$GJALDEYRIR':
		embed.add_field(name="Gjaldeyrir:", value=", ".join(forex), inline=False)
		embed.add_field(name="Eiginleikar:", value="Gjaldeyrir er hugtak sem haft er um erlendan gjaldmiðil sem keyptur er í samræmi við gengi myntarinnar. Ekki er tekið gjald fyrir viðskipti með gjaldeyri. EUR og USD bera 1% vexti á ársgrundvelli, greiddir út daglega í hádeginu, sem leggst sjálfkrafa inn á DEBET-reikninginn. BTC ber enga vexti.", inline=False)
		embed.add_field(name="Meiri upplýsingar:", value="Skráðu inn $<merki>, t.d. $USD fyrir frekari upplýsingar um einstaka gjaldmiðla. Skráðu inn $kaupa <merki> <upphæð> eða $selja <merki> <upphæð> fyrir kaup eða sölu á gjaldeyri.", inline=False)
		await message.channel.send(embed=embed)
		return

	if msg == '$SJODIR':
		embed.add_field(name="Sjóðir:", value=", ".join(funds), inline=False)
		embed.add_field(name="Eiginleikar:", value="Hlutabréfasjóður er sjóður sem tekur við fé eða fjármagni til sameiginlegrar fjárfestingar í hlutabréfum einstaka fyrirtækja eða öðrum hlutabréfasjóðum. Tekið er gjald á kaupum á hlutdeildarskírteinum, 1.5%. Eignir sjóðsins geta greitt út arð en hann er endurfjárfestur í sjóðnum sjálfum.", inline=False)
		embed.add_field(name="Meiri upplýsingar:", value="Skráðu inn $<merki>, t.d. $VFIAX fyrir frekari upplýsingar um einstaka sjóði. Skráðu inn $kaupa <merki> <upphæð> eða $selja <merki> <upphæð> fyrir kaup eða sölu á hlutdeildarskírteinum í sjóðum.", inline=False)
		await message.channel.send(embed=embed)
		return

	if msg.startswith('$EIGNIR'):
		if msg == '$EIGNIR':
			assets_info = get_assets_info(message.guild.id, message.author.id)
			if len(assets_info) == 0:
				embed.add_field(name="Þú hefur ekki stofnað vörslureikning enn.", value="Sláðu inn '$stofna' til að stofna vörslureikning eða '$hjálp' fyrir aðstoð.", inline=False)
				await message.channel.send(embed=embed)
				return
			net_worth = 0
			for asset_type, ticker, volume in assets_info:
				worth = math.floor(volume*get_price_by_type(asset_type, ticker))
				net_worth = net_worth + worth
				embed.add_field(name="{} - {}".format(asset_type, ticker), value="Magn: {0}\nVirði: {1} kr.".format(volume, worth), inline=False)
			embed.add_field(name="Samtals:", value="Virði: {0} kr.".format(net_worth), inline=False)
			await message.channel.send(embed=embed)
			return
		elif msg.startswith('$EIGNIR <@'):
			try:
				user_id = int(msg.split(' ')[1][3:-1])
				print(user_id)
				assets_info = get_assets_info(message.guild.id, user_id)
				if len(assets_info) == 0:
					embed.add_field(name="Villa", value="{} hefur ekki stofnað vörslureikning enn.".format(client.get_user(user_id).display_name), inline=False)
					await message.channel.send(embed=embed)
					return
				net_worth = 0
				for asset_type, ticker, volume in assets_info:
					worth = math.floor(volume*get_price_by_type(asset_type, ticker))
					net_worth = net_worth + worth
					embed.add_field(name="{} - {}".format(asset_type, ticker), value="Magn: {0}\nVirði: {1} kr.".format(volume, worth), inline=False)
				embed.add_field(name="Samtals:", value="Virði: {0} kr.".format(net_worth), inline=False)
				await message.channel.send(embed=embed)
				return
			except:
				embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt skoða. Prófaðu '$hjálp'.", inline=False)
				await message.channel.send(embed=embed)
				return

	if msg == '$STIGATAFLA':
		scores = get_scores(message.guild.id)
		for idx, score in enumerate(scores):
			print(score)
			print(client.get_user(369527993208668160))
			embed.add_field(name="{}. {}".format(idx+1, client.get_user(score[0]).display_name), value="{} kr. ({}%)".format(math.floor(score[1]), math.floor((score[1]/1000000-1)*100)), inline=False)
		await message.channel.send(embed=embed)
		return

	if msg[1:] in stocks:
		price_now, price_year_ago, description, url = get_stock_info(msg[1:])
		embed.add_field(name=msg[1:], value="Verð núna: {:.2f} kr.\nVerð fyrir ári {:.2f} kr. ({:.2f}%)".format(price_now, price_year_ago, (price_now/price_year_ago*100)-100), inline=False)
		embed.add_field(name="Upplýsingar", value="{0}...\n[Hlekkur]({1})".format(description[:500], url), inline=False)
		await message.channel.send(embed=embed)
		return

	if msg[1:] in forex:
		price_now, price_year_ago = get_currency_info(msg[1:])
		embed.add_field(name=msg[1:], value="Verð núna: {:.2f} kr.\nVerð fyrir ári {:.2f} kr. ({:.2f}%)".format(price_now, price_year_ago, (price_now/price_year_ago*100)-100), inline=False)
		await message.channel.send(embed=embed)
		return

	if msg[1:] in funds:
		price_now, price_year_ago = get_fund_info(msg[1:])
		embed.add_field(name="{} - {}".format(msg[1:], get_fund_from_ticker(msg[1:])), value="Verð núna: {:.2f} kr.\nVerð fyrir ári {:.2f} kr. ({:.2f}%)".format(price_now, price_year_ago, (price_now/price_year_ago*100)-100), inline=False)
		await message.channel.send(embed=embed)
		return

	if msg.startswith('$KAUPA'):
		cmd = msg.split()
		if len(cmd) == 3:
			try:
				amount = int(cmd[2])
				ticker = cmd[1]
				if ticker in stocks:
					embed.add_field(name="Kauptilboð - {0}".format(ticker), value="Þú hefur óskað eftir kaupum á hlutbréfum í {0}.".format(ticker), inline=False)
					price = get_stock_price(ticker)
					volume = math.floor((amount - math.ceil(amount*stock_commission)) / price)
					final_amount = math.ceil(price*volume)
					final_costs = math.ceil(price*volume*stock_commission)
					embed.add_field(name="Upplýsingar:", value="Verð per hlut: {0} kr.\nKostnaður: {1} kr.\nFjöldi hluta: {2}\nHeildarverð: {3} kr.".format(price, final_costs, volume, final_amount), inline=False)
					debet_status = get_debet_status(message.guild.id, message.author.id)
					if debet_status is None:
						embed.add_field(name="Þú hefur ekki stofnað vörslureikning enn.", value="Sláðu inn '$stofna' til að stofna vörslureikning eða '$hjálp' fyrir aðstoð.", inline=False)
						await message.channel.send(embed=embed)
						return
					if debet_status >= final_amount:
						make_purchase_transaction(message.guild.id, message.author.id, "Stock", ticker, volume, final_amount+final_costs)
						embed.add_field(name="Greiðsla tókst.", value="Nýir hlutir í {} hafa verið afhentir.".format(ticker), inline=False)
						await message.channel.send(embed=embed)
						return
					embed.add_field(name="Greiðsla tókst ekki.", value="Staða á DEBET-reikningi ekki nægjanleg.", inline=False)
					await message.channel.send(embed=embed)
					return
				elif ticker in funds:
					embed.add_field(name="Kauptilboð - {0}".format(ticker), value="Þú hefur óskað eftir kaupum á hlutdeildarskírteinum í {0}.".format(ticker), inline=False)
					price = get_fund_price(ticker)
					volume = (amount - math.ceil(amount*fund_commission)) / price
					final_amount = math.ceil(price*volume)
					final_costs = math.ceil(price*volume*fund_commission)
					embed.add_field(name="Upplýsingar:", value="Verð per hlut: {0} kr.\nKostnaður: {1} kr.\nFjöldi hluta: {2}\nHeildarverð: {3} kr.".format(price, final_costs, volume, final_amount), inline=False)
					debet_status = get_debet_status(message.guild.id, message.author.id)
					if debet_status is None:
						embed.add_field(name="Þú hefur ekki stofnað vörslureikning enn.", value="Sláðu inn '$stofna' til að stofna vörslureikning eða '$hjálp' fyrir aðstoð.", inline=False)
						await message.channel.send(embed=embed)
						return
					if debet_status >= final_amount:
						make_purchase_transaction(message.guild.id, message.author.id, "Fund", ticker, volume, final_amount+final_costs)
						embed.add_field(name="Greiðsla tókst.", value="Nýir hlutir í {} hafa verið afhentir.".format(ticker), inline=False)
						await message.channel.send(embed=embed)
						return
					embed.add_field(name="Greiðsla tókst ekki.", value="Staða á DEBET-reikningi ekki nægjanleg.", inline=False)
					await message.channel.send(embed=embed)
					return
				elif ticker in forex:
					embed.add_field(name="Kauptilboð - {0}".format(ticker), value="Þú hefur óskað eftir kaupum á {0} gjaldeyri.".format(ticker), inline=False)
					price = get_currency_price(ticker)
					if ticker in ["USD","EUR"]:
						volume = math.floor((amount/price)*100)/100.0
					else:
						volume = truncate(amount/price, 8)
					final_amount = math.ceil(volume*price)
					final_costs = 0
					embed.add_field(name="Upplýsingar:", value="Verð per {4}: {0} kr.\nKostnaður: {1} kr.\nFjöldi {4}: {2}\nHeildarverð: {3} kr.".format(price, final_costs, volume, final_amount, ticker), inline=False)
					debet_status = get_debet_status(message.guild.id, message.author.id)
					if debet_status is None:
						embed.add_field(name="Þú hefur ekki stofnað vörslureikning enn.", value="Sláðu inn '$stofna' til að stofna vörslureikning eða '$hjálp' fyrir aðstoð.", inline=False)
						await message.channel.send(embed=embed)
						return
					if debet_status >= final_amount:
						make_purchase_transaction(message.guild.id, message.author.id, "Currency", ticker, volume, final_amount+final_costs)
						embed.add_field(name="Greiðsla tókst.", value="Gjaldmiðill {} hefur verið afhentur.".format(ticker), inline=False)
						await message.channel.send(embed=embed)
						return
					embed.add_field(name="Greiðsla tókst ekki.", value="Staða á DEBET-reikningi ekki nægjanleg.", inline=False)
					await message.channel.send(embed=embed)
					return
				else:
					embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt kaupa. Prófaðu '$hjálp'.", inline=False)
					await message.channel.send(embed=embed)
					return
			except:
				embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt kaupa. Prófaðu '$hjálp'.", inline=False)
				await message.channel.send(embed=embed)
				return
		else:
			embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt kaupa. Prófaðu '$hjálp'.", inline=False)
			await message.channel.send(embed=embed)
			return

	if msg.startswith('$SELJA'):
		cmd = msg.split()
		if len(cmd) == 3:
			try:
				amount = int(cmd[2])
				ticker = cmd[1]
				if ticker in stocks:
					embed.add_field(name="Sölutilboð - {0}".format(ticker), value="Þú hefur óskað eftir sölu á hlutbréfum í {0}.".format(ticker), inline=False)
					price = get_stock_price(ticker)
					#volume = math.floor((amount - math.ceil(amount*stock_commission)) / price)
					volume = math.floor(amount/price)
					final_amount = math.ceil(price*volume)
					final_costs = math.ceil(price*volume*stock_commission)
					embed.add_field(name="Upplýsingar:", value="Verð per hlut: {0} kr.\nKostnaður: {1} kr.\nFjöldi hluta: {2}\nHeildarverð: {3} kr.".format(price, final_costs, volume, final_amount), inline=False)
					security_status = get_security_status(message.guild.id, message.author.id, ticker)
					if security_status is None:
						embed.add_field(name="Þú átt engar eignir í {} til að selja.".format(ticker), value="Sláðu inn '$stofna' til að stofna vörslureikning, '$kaupa <merki> <upphæð>' til að kaupa eða '$hjálp' fyrir aðstoð.", inline=False)
						await message.channel.send(embed=embed)
						return
					elif security_status >= volume:
						make_sale_transaction(message.guild.id, message.author.id, "Stock", ticker, volume, final_amount)
						embed.add_field(name="Sala tókst.", value="{0} kr. hafa verið lagðar inn á þig.".format(final_amount), inline=False)
						await message.channel.send(embed=embed)
						return
					embed.add_field(name="Sala tókst ekki.", value="Þú átt ekki nægjanlega mikið í {0} fyrir söluna.".format(ticker), inline=False)
					await message.channel.send(embed=embed)
					return
				elif ticker in funds:
					embed.add_field(name="Sölutilboð - {0}".format(ticker), value="Þú hefur óskað eftir sölu á hlutdeildarskírteinum í {0}.".format(ticker), inline=False)
					price = get_fund_price(ticker)
					volume = amount/price
					final_amount = math.ceil(price*volume)
					final_costs = 0
					embed.add_field(name="Upplýsingar:", value="Verð per hlut: {0} kr.\nKostnaður: {1} kr.\nFjöldi hluta: {2}\nHeildarverð: {3} kr.".format(price, final_costs, volume, final_amount), inline=False)
					security_status = get_security_status(message.guild.id, message.author.id, ticker)
					if security_status is None:
						embed.add_field(name="Þú hefur ekki stofnað vörslureikning enn.", value="Sláðu inn '$stofna' til að stofna vörslureikning eða '$hjálp' fyrir aðstoð.", inline=False)
						await message.channel.send(embed=embed)
						return
					if security_status >= volume:
						make_sale_transaction(message.guild.id, message.author.id, "Fund", ticker, volume, final_amount)
						embed.add_field(name="Sala tókst.", value="{0} kr. hafa verið lagðar inn á þig.".format(final_amount), inline=False)
						await message.channel.send(embed=embed)
						return
					embed.add_field(name="Sala tókst ekki.", value="Þú átt ekki nægjanlega mikið í {0} fyrir söluna.".format(ticker), inline=False)
					await message.channel.send(embed=embed)
					return
				elif ticker in forex:
					embed.add_field(name="Sölutilboð - {0}".format(ticker), value="Þú hefur óskað eftir sölu á {0} gjaldeyri.".format(ticker), inline=False)
					price = get_currency_price(ticker)
					if ticker in ["USD","EUR"]:
						volume = math.floor((amount/price)*100)/100.0
					else:
						volume = truncate(amount/price, 8)
					final_amount = math.ceil(volume*price)
					final_costs = 0
					embed.add_field(name="Upplýsingar:", value="Verð per {4}: {0} kr.\nKostnaður: {1} kr.\nFjöldi {4}: {2}\nHeildarverð: {3} kr.".format(price, final_costs, volume, final_amount, ticker), inline=False)
					security_status = get_security_status(message.guild.id, message.author.id, ticker)
					if security_status is None:
						embed.add_field(name="Þú átt engar eignir í {} til að selja.".format(ticker), value="Sláðu inn '$stofna' til að stofna vörslureikning, '$kaupa <merki> <upphæð>' til að kaupa eða '$hjálp' fyrir aðstoð.", inline=False)
						await message.channel.send(embed=embed)
						return
					elif security_status >= volume:
						make_sale_transaction(message.guild.id, message.author.id, "Currency", ticker, volume, final_amount)
						embed.add_field(name="Sala tókst.", value="{0} kr. hafa verið lagðar inn á þig.".format(final_amount), inline=False)
						await message.channel.send(embed=embed)
						return
					embed.add_field(name="Sala tókst ekki.", value="Þú átt ekki nægjanlega mikið í {0} fyrir söluna.".format(ticker), inline=False)
					await message.channel.send(embed=embed)
					return
				else:
					embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt selja. Prófaðu '$hjálp'.", inline=False)
					await message.channel.send(embed=embed)
					return
			except:
				embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt selja. Prófaðu '$hjálp'.", inline=False)
				await message.channel.send(embed=embed)
				return
		else:
			embed.add_field(name="Villa", value="Ég skil ekki hvað þú vilt selja. Prófaðu '$hjálp'.", inline=False)
			await message.channel.send(embed=embed)
			return

	return

client.run(token)