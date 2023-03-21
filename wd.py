import os
import sys
import datetime
import html
import requests
import json

import osmapi
from loguru import logger

from OSMCacheIterator import ArrayCacheIterator

import Settings


sys.stdin.reconfigure(encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')

logger.add(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".log", "osm.log"))


def GetNodesInWays(Ways):
 Nodes = []
 for Item in ArrayCacheIterator(256, Ways, "way"):
  Nodes += Item['nd']
 return GetNodes(Nodes)


def GetNodes(Nodes):
 return [ {'type': "node", 'data': {'lat': Item['lat'], 'lon': Item['lon']}} for Item in ArrayCacheIterator(256, Nodes, "node") ]


def IsRect(Item):
 if Item:
  if Item['type'] == "node":
#   print(Item)
   Data = Item['data']
#   print(Data)
#   print(f"{Settings.MinLat} <= {Data['lat']} <= {Settings.MaxLat} and {Settings.MinLon} <= {Data['lon']} <= {Settings.MaxLon} | {Settings.MinLat <= Data['lat'] <= Settings.MaxLat and Settings.MinLon <= Data['lon'] <= Settings.MaxLon}")
   return Settings.MinLat <= Data.get('lat', 0) <= Settings.MaxLat and Settings.MinLon <= Data.get('lon', 0) <= Settings.MaxLon
  #
  if Item['type'] == "way":
   Data = Item['data']
   for Node in GetNodes(Data['nd']):
#    print("Node", Node)
    if IsRect(Node):
     return True
  #
  if Item['type'] == "relation":
   Data = Item['data']
   Member = Data['member']
   Nodes = { 'type': "way", 'data': { 'nd': [ Item['ref'] for Item in Member if Item['type'] == "node" ] } }
#   print("Nodes", Nodes)
   for Node in GetNodes(Nodes['data']['nd']):
#    print("Node", Node)
    if IsRect(Node):
     return True
   #
   Ways = [ Item['ref'] for Item in Member if Item['type'] == "way" ]
   Nodes = GetNodesInWays(Ways)
#   print("Ways", Nodes)
   for Node in Nodes:
#    print("Node", Node)
    if IsRect(Node):
     return True
   #
   Relations = [ { 'type': "relation", 'data': {'type': "relation", 'ref': Item['ref'] } } for Item in Member if Item['type'] == "relation" ]
#   print("Relations", Relations)
   if IsRect(Relations):
    return True
 #
 return False





# Разбирает структуру "области" и делает запрос к сайту ОСМ
# Отдает разобранный чейнджсет
def SendMessages(Date):
 Result = []
 OSM = osmapi.OsmApi()
 # запрос к сайту ОСМ
 try:
  Changesets = OSM.ChangesetsGet(Settings.MinLon, Settings.MinLat, Settings.MaxLon, Settings.MaxLat, closed_after=Date)
 except:
  logger.error("No new changesets")
  Changesets = {}
 # формируем строки изменений
 for Key, Values in Changesets.items():
  logger.info(f"Check changeset {Key}")
  Is = False
  ChangesCount = { 'node': {'create': 0, 'modify': 0, 'delete': 0}, 'way': {'create': 0, 'modify': 0, 'delete': 0}, 'relation': {'create': 0, 'modify': 0, 'delete': 0} }
  for Item in OSM.ChangesetDownload(Key):
   ChangesCount[Item['type']][Item['action']] += 1
   if IsRect(Item):
    Is = True
  if Is:
   #Changes = "\n".join([f"{k}: {v}" for k, v in ChangesCount.items()])
   Table = []
   for k1, v1 in ChangesCount.items():
    if not Table:
     Table.append(" ".rjust(8) + " " + " ".join(v1))
    L = [(f"{v2}" if v2 > 0 else "").rjust(6) for k2, v2 in v1.items() ]
    Table.append(k1.rjust(8) + " " + " ".join(L))
   Changes = "\n".join(Table)
   Tag = "\n".join([f"{k} = {v}" for k, v in Values['tag'].items()])
   # формируем сообщения
   Message = [ f"<i>{Values['created_at']}</i>", f"<b>#{Values['id']}</b> <a href='http://hdyc.neis-one.org/?{Values['user']}'>{html.escape(Values['user'])}</a>", "----------", f"<pre>{Changes}</pre>", "----------", f"<i>{Tag}</i>"]
   Result.append("\n".join(Message))
   #print("\n".join(Message))
   Send(Values['id'], "\n".join(Message))

 return Result


def Send(ID, Message):
 Method = "/sendMessage"
 Url = f"https://api.telegram.org/bot{Settings.Token}{Method}"
 View = [
  { 'text': "OSM", 'url': f"http://www.openstreetmap.org/changeset/{ID}" },
  { 'text': "Achavi", 'url': f"http://overpass-api.de/achavi/?changeset={ID}" },
  { 'text': "OSMCHA", 'url': f"https://osmcha.mapbox.com/{ID}" },
  { 'text': "JOSM", 'url': f"http://127.0.0.1:8111/import?url=http://www.openstreetmap.org/changeset/{ID}" },
 ]
 Reply = json.dumps({'inline_keyboard': [View]})
 Request = requests.post(Url, data={'chat_id': Settings.UserID, 'text': Message, 'parse_mode': "HTML", 'disable_web_page_preview': True, 'reply_markup': Reply })
 logger.info(Request.text)
 if Request.status_code != 200:
  logger.error("post_text error")
  raise Exception("post_text error")



def main():

 logger.info("Start")

 Now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
 if os.path.isfile("wd.txt"):
  with open("wd.txt", 'r') as f:
   Date = f.readline()
 else:
  Date = datetime.date.today().strftime("%Y-%m-%dT%H:%M:%SZ")

 SendMessages(Date)

 with open("wd.txt", 'w') as f:
  f.write(Now)
 #print(Date, Now)

 logger.info("Done")


if __name__ == '__main__':
 main()
