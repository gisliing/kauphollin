import sqlite3

debet_interest = 0.025/365.0
forex_interest = 0.010/365.0

conn = sqlite3.connect('kaupholl.db')
c = conn.cursor()

c.execute('''UPDATE ASSETS
			 SET VOLUME = (CAST (VOLUME * ? AS INT))
			 WHERE TICKER = "DEBET";''', [1 + debet_interest])

c.execute('''UPDATE ASSETS
			 SET VOLUME = ROUND(VOLUME * ?,2)
			 WHERE TICKER IN ("USD","EUR");''', [1 + forex_interest])

conn.commit()