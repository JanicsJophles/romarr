"""Read-only client telemetry. Never send client URLs or credentials to browsers."""
import threading,time,math
LOCK=threading.Lock();CACHE={'at':0,'rows':[],'errors':[]}
def number(value,default=0):
 try:
  result=float(value)
  return result if math.isfinite(result) else default
 except (ValueError,TypeError):return default
def qbit_row(x):
 state=str(x.get('state') or '');progress=min(1,max(0,number(x.get('progress'))))
 status='downloading';detail=''
 if state in ('metaDL','forcedMetaDL'):status='metadata';detail='Waiting for torrent metadata from peers; no game data yet.'
 elif state in ('error','missingFiles'):status='failed';detail='Download client reports '+state
 elif state in ('pausedDL','stoppedDL'):status='paused'
 elif state=='stalledDL':status='stalled';detail='No data arriving from peers.'
 elif state.startswith('checking'):status='verifying'
 elif progress>=1:status='downloaded';detail='Download complete; awaiting library import.'
 return {'release':x.get('name',''),'client':'qBittorrent','status':status,'detail':detail,'progress':round(progress*100,1),'speed':max(0,number(x.get('dlspeed'))),'eta_seconds':number(x.get('eta')) if x.get('eta') is not None and 0<=number(x.get('eta'),8640000)<8640000 else None,'peers':int(max(0,number(x.get('num_seeds')))+max(0,number(x.get('num_leechs')))),'size':x.get('size',0),'downloaded':x.get('downloaded',0)}
def sab_row(x,history=False):
 state=str(x.get('status',''));status={'Downloading':'downloading','Paused':'paused','Queued':'queued','Fetching':'metadata','Completed':'downloaded','Failed':'failed','Verifying':'verifying','Repairing':'repairing','Extracting':'extracting','Moving':'importing'}.get(state,'processing')
 return {'release':x.get('name') or x.get('filename',''),'client':'SABnzbd','status':status,'detail':'SABnzbd reports failure. Review client history before retrying.' if state=='Failed' else state,'progress':100 if state=='Completed' else min(100,max(0,number(x.get('percentage')))),'timeleft':x.get('timeleft',''),'size':int(max(0,number(x.get('mb')))*1048576),'downloaded':int((max(0,number(x.get('mb')))-max(0,number(x.get('mbleft'))))*1048576)}
def snapshot(service):
 with LOCK:
  if time.monotonic()-CACHE['at']<8:return CACHE.copy()
  rows=[];errors=[]
  for c in service.clients:
   try:
    if c.__class__.__name__=='QBittorrent':
     r=c._get('torrents/info',params={'category':c._config.category},timeout=5);r.raise_for_status();rows.extend(qbit_row(x) for x in r.json())
    elif c.__class__.__name__=='SABnzbd':
     for mode in ('history','queue'):
      d=c._call(mode,_timeout=5,limit=100,category=c._config.category)
      if d is None:raise RuntimeError('Unavailable')
      for x in d.get(mode,{}).get('slots',[]):
       if x.get('cat',x.get('category',c._config.category))==c._config.category:rows.append(sab_row(x,mode=='history'))
   except Exception:errors.append(getattr(c,'name','Download client')+' unavailable')
  CACHE.update(at=time.monotonic(),rows=rows,errors=errors)
  return CACHE.copy()
def enrich(service,rows):
 live=snapshot(service);by_name={x['release'].casefold():x for x in live['rows']}
 for row in rows:
  row['checked_at']=time.time()
  if row['status'] in ('imported','searching'):continue
  match=by_name.get(row.get('release','').casefold())
  if match:row.update(match)
  elif row['status']=='downloading':row.update(status='unknown',detail='; '.join(live['errors']) or 'Accepted earlier, but no matching download is currently visible. Check the client.')
 return rows
