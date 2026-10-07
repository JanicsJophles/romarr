"""Read-only client telemetry. Never send client URLs or credentials to browsers."""
import threading,time,math
from .download_identity import safe_job_id, matches_job
LOCK=threading.Lock();CACHE={'at':0,'rows':[],'errors':[],'client_warnings':[],'service':None}
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
 return {'job_id':safe_job_id(x.get('hash')),'release':x.get('name',''),'client':'qBittorrent','status':status,'detail':detail,'progress':round(progress*100,1),'speed':max(0,number(x.get('dlspeed'))),'eta_seconds':number(x.get('eta')) if x.get('eta') is not None and 0<=number(x.get('eta'),8640000)<8640000 else None,'peers':int(max(0,number(x.get('num_seeds')))+max(0,number(x.get('num_leechs')))),'size':x.get('size',0),'downloaded':x.get('downloaded',0)}
def sab_row(x,history=False):
 from .download_failures import DETAILS,sab_failure_code
 state=str(x.get('status',''));status={'Downloading':'downloading','Paused':'paused','Queued':'queued','Fetching':'metadata','Completed':'downloaded','Failed':'failed','Verifying':'verifying','Repairing':'repairing','Extracting':'extracting','Moving':'importing'}.get(state,'processing')
 return {'job_id':safe_job_id(x.get('nzo_id')),'release':x.get('name') or x.get('filename',''),'client':'SABnzbd','status':status,'detail':DETAILS.get(sab_failure_code(x.get('fail_message')),'SABnzbd reports failure. Review client history before retrying.') if state=='Failed' else state,'progress':100 if state=='Completed' else min(100,max(0,number(x.get('percentage')))),'timeleft':x.get('timeleft',''),'size':int(max(0,number(x.get('mb')))*1048576),'downloaded':int((max(0,number(x.get('mb')))-max(0,number(x.get('mbleft'))))*1048576)}
def snapshot(service, *, force=False):
 with LOCK:
  if not force and CACHE.get('service') is service and time.monotonic()-CACHE['at']<8:return CACHE.copy()
  rows=[];errors=[];warnings=[]
  for c in service.clients:
   if not getattr(c,'configured',True):continue
   try:
    if c.__class__.__name__=='QBittorrent':
     r=c._get('torrents/info',params={'category':c._config.category},timeout=5);r.raise_for_status();jobs=r.json()
     from .network_diagnostics import inspect_qbit
     network=inspect_qbit(c,jobs)
     if network['status'] in ('dns-errors','tracker-errors'):
      warnings.append({'client':'qBittorrent','status':network['status'],'detail':network['detail']})
     for job in jobs:
      row=qbit_row(job)
      row['network_status']=network['status'];row['network_detail']=network['detail']
      if row['status'] in ('metadata','stalled') and network['status'] in ('dns-errors','tracker-errors'):
       row['detail']+=' '+network['detail']
      rows.append(row)
    elif c.__class__.__name__=='SABnzbd':
     for mode in ('history','queue'):
      d=c._call(mode,_timeout=5,limit=100,category=c._config.category)
      if d is None:raise RuntimeError('Unavailable')
      for x in d.get(mode,{}).get('slots',[]):
       if x.get('cat',x.get('category',c._config.category))==c._config.category:rows.append(sab_row(x,mode=='history'))
   except Exception:
    label={'QBittorrent':'qBittorrent','SABnzbd':'SABnzbd'}.get(c.__class__.__name__,'Download client')
    errors.append(label+' unavailable')
    warnings.append({'client':label,'status':'unavailable','detail':'Could not read this download client. Check its connection and settings; saved request outcomes have not changed.'})
  CACHE.update(at=time.monotonic(),rows=rows,errors=errors,client_warnings=warnings,service=service)
  return CACHE.copy()
def enrich(service,rows,live=None):
 """Overlay unambiguous live telemetry without erasing durable outcomes.

 A completed client download is not a successful library import. Likewise,
 history for a previous attempt must not revive a failed request. Client names
 narrow title matching; duplicate titles remain unknown until we track job IDs.
 """
 if live is None:live=snapshot(service)
 # A report belongs to one attempt, even if that attempt is no longer the
 # latest projected request. Never lend an old known job to a title-only row.
 claimed={(r.get('client',''),r.get('download_job_id','')) for r in rows if r.get('download_job_id')}
 queue=getattr(service,'queue',None)
 if isinstance(queue,(list,tuple)):
  claimed.update((getattr(q,'download_client',''),getattr(q,'download_job_id',''))
                 for q in queue if getattr(q,'download_job_id',''))
 def available_to(row, report):
  if row.get('download_job_id'):return True
  job=report.get('job_id')
  if job and any(job==owned and (not client or client==report.get('client')) for client,owned in claimed):return False
  # Legacy matching must be unique in both directions, not just one report
  # per row: two saved requests must not both claim a single download.
  owners=[r for r in rows if not r.get('download_job_id') and
          matches_job('',r.get('client',''),r.get('release',''),report)]
  return len(owners)==1
 for row in rows:
  row['checked_at']=time.time()
  if row['status'] in ('imported','searching'):continue
  release=row.get('release','').casefold()
  matches=[x for x in live['rows'] if matches_job(row.get('download_job_id',''),row.get('client',''),release,x) and available_to(row,x)]
  if len(matches)==1:
   match=matches[0]
   if row['status'] in ('failed','import-failed'):
    # A tracking/import outcome and current client activity are different facts.
    # Keep both visible without reviving the request or scheduling a retry.
    row.update(client_status=match['status'],client_detail=match.get('detail',''),
               client_progress=match.get('progress'))
    if match.get('network_status'):
     row.update(network_status=match['network_status'],network_detail=match['network_detail'])
    if ('no import after' in row.get('detail','').casefold()
        or 'timed out' in row.get('detail','').casefold()):
     if match['status']=='metadata':
      row['client_detail']='Request tracking timed out; the downloader is still waiting for metadata. No game data has arrived.'
      if match.get('network_status') in ('dns-errors','tracker-errors'):
       row['client_detail']+=' '+match['network_detail']
   else:row.update(match)
  elif row['status'] in ('downloading','queued'):
   detail=('Multiple matching downloads are visible. Review the client to identify this request.'
           if len(matches)>1 else '; '.join(live['errors']) or
           'Accepted earlier, but no matching download is currently visible. Check the client.')
   row.update(status='unknown',detail=detail)
 return rows
