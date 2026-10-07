"""Durable, idempotent browser requests; download truth remains in ROMarr queue."""
import hashlib,json,threading,time,os
from pathlib import Path
from .platforms import resolve
LOCK=threading.RLock()
PATH=Path('/config/game-requests.json')
ACTIVE=set()
def key(game,platform):return hashlib.sha256((game.strip().casefold()+'|'+platform).encode()).hexdigest()[:24]
def load():
 if not PATH.exists():return {}
 try:
  rows=json.loads(PATH.read_text())
  if not isinstance(rows,dict) or any(not isinstance(row,dict) for row in rows.values()):raise ValueError()
  return rows
 except (ValueError,TypeError):raise ValueError('Request history cannot be read. Restore its backup before sending new requests.')
def save(rows):
 p=PATH.with_suffix('.tmp');p.write_text(json.dumps(rows));p.chmod(0o600)
 with p.open('rb') as f:os.fsync(f.fileno())
 p.replace(PATH)
def base_status(service):
 with LOCK:
  rows=load()
  for item in service.queue:
   k=key(item.game,item.platform)
   row=rows.setdefault(k,{'id':k,'game':item.game,'platform':item.platform})
   row.update(status={'grabbed':'downloading','queued':'queued','imported':'imported','failed':'failed'}.get(item.state,item.state),detail=item.detail,release=item.release,client=getattr(item,"download_client",""),indexer=getattr(item,"indexer",""),indexer_seeders=getattr(item,"seeders",None),review_required=getattr(item,"review_required",False),download_job_id=getattr(item,"download_job_id",""))
  for w in service.store.missing():
   k=key(w['game'],w['platform'])
   rows.setdefault(k,{'id':k,'game':w['game'],'platform':w['platform'],'status':'wanted','detail':w.get('last_error','')})
  for k,row in rows.items():
   if k in ACTIVE:row['status']='searching'
   elif row.get('status')=='searching':row.update(status='interrupted',detail='The server restarted during this search. Review Queue before retrying.')
  save(rows)
  return list(rows.values())
def submit(service,body):
 if not isinstance(body,dict) or not isinstance(body.get('game'),str) or not isinstance(body.get('platform'),str):raise ValueError('Choose a game and a supported platform.')
 game=body['game'].strip();plat=resolve(body['platform'])
 if not game or len(game)>200 or not plat:raise ValueError('Choose a game and a supported platform.')
 k=key(game,plat.slug)
 with LOCK:
  previous=next((r for r in base_status(service) if r['id']==k),None)
  if previous:return {'accepted':True,'duplicate':True,'request':previous}
  if len(ACTIVE)>=2:return {'error':'Two requests are searching. Wait for one to finish.'}
  rows=load();row={'id':k,'game':game,'platform':plat.slug,'status':'searching','created':time.time(),'detail':'Searching configured indexers'};rows[k]=row;save(rows);ACTIVE.add(k)
  def worker():
   try:
    result=service.request(game,plat.slug)
    state='downloading' if result.get('ok') else 'failed';detail='Handed to download client' if result.get('ok') else 'No release was accepted. Review search results and client settings.'
   except Exception:
    state='failed';detail='Search failed. Check Indexers and Queue before trying again.'
   finally:
    with LOCK:
     try:
      rows=load();rows[k].update(status=state,detail=detail);save(rows)
     finally:ACTIVE.discard(k)
  try:threading.Thread(target=worker,daemon=True).start()
  except Exception:
   ACTIVE.discard(k)
   raise ValueError('Could not start the search. Review Queue before retrying.')
  return {'accepted':True,'request':dict(row)}

def status_payload(service):
 reconcile=getattr(service,"reconcile_client_failures",None)
 if callable(reconcile):reconcile()
 from .download_status import enrich,snapshot
 live=snapshot(service)
 return {'items':enrich(service,base_status(service),live=live),
         'client_warnings':live.get('client_warnings',[])}

def all_status(service):
 return status_payload(service)['items']
