#!/usr/bin/env python3
"""Offline chirp library: schema checks, repeat-aware selection, and Piper caching."""
import argparse, hashlib, json, random, re, sqlite3, subprocess, sys, time
from pathlib import Path
from urllib.request import Request, urlopen

BIRDS={'jose','michael','fritz','pierre','polly'}
MAIN=BIRDS-{'polly'}
TYPES={'joke','roast','compliment','greeting','farewell','question','comeback','idle','banter'}
TRIGGERS={'person_detected','person_approaching','person_departing','interaction','idle','manual','event','voice_command'}
TABLES='''
CREATE TABLE IF NOT EXISTS chirps(id TEXT PRIMARY KEY,family_id TEXT NOT NULL,speaker TEXT NOT NULL, body TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS plays(id INTEGER PRIMARY KEY AUTOINCREMENT,chirp_id TEXT NOT NULL,family_id TEXT NOT NULL,played_at REAL NOT NULL,session_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS listeners(play_id INTEGER NOT NULL,listener_id TEXT NOT NULL,PRIMARY KEY(play_id,listener_id));
CREATE INDEX IF NOT EXISTS idx_plays_family_time ON plays(family_id,played_at);
CREATE INDEX IF NOT EXISTS idx_listeners_listener ON listeners(listener_id);
CREATE TABLE IF NOT EXISTS audio_cache(cache_key TEXT PRIMARY KEY,chirp_id TEXT NOT NULL,audio BLOB NOT NULL,cues TEXT NOT NULL,created_at REAL NOT NULL);
'''

def connect(path):
    db=sqlite3.connect(path)
    db.row_factory=sqlite3.Row
    db.executescript(TABLES)
    return db

def validate(ch):
    if not isinstance(ch,dict): raise ValueError('chirp must be an object')
    for k in ('id','family_id','text','speaker','type','required_tags','optional_tags','excluded_tags','tags','trigger','audience'):
        if k not in ch: raise ValueError(f'missing {k}')
    if not isinstance(ch['id'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{2,100}',ch['id']): raise ValueError('invalid id')
    if not isinstance(ch['family_id'],str) or not ch['family_id'].strip(): raise ValueError('invalid family_id')
    if not isinstance(ch['text'],str) or not ch['text'].strip(): raise ValueError('missing text')
    if ch['speaker'] not in BIRDS and ch['speaker']!='any': raise ValueError('invalid speaker')
    if ch['type'] not in TYPES or ch['trigger'] not in TRIGGERS: raise ValueError('invalid type/trigger')
    if ch['audience'] not in {'all_ages','adults'}: raise ValueError('invalid audience')
    for k in ('required_tags','optional_tags','excluded_tags','tags'):
        if not isinstance(ch[k],list) or any(not isinstance(x,str) or not re.fullmatch(r'[a-z0-9_]+',x) for x in ch[k]):raise ValueError('invalid '+k)
    if ch['speaker']=='polly':
        if ch['audience']!='adults' or ch.get('min_age')!=18 or 'adult_mode' not in ch['required_tags']:raise ValueError('Polly requires adult mode and age 18 restriction')
        if ch.get('dialogue'): raise ValueError('Polly cannot appear in dialogue')
    if ch['speaker']=='any' and ch['audience']=='adults':
        # Generic adult content must still explicitly target a named main bird.
        raise ValueError('adult entries must name a speaker')
    dialogue=ch.get('dialogue',[])
    if dialogue:
        if ch['speaker']=='polly' or ch['type']!='banter' or not isinstance(dialogue,list):raise ValueError('invalid dialogue')
        if any(not isinstance(l,dict) or l.get('speaker') not in MAIN or not isinstance(l.get('text'),str) for l in dialogue):raise ValueError('dialogue must use main birds exclusively')
        if ch['speaker'] not in MAIN or ch['text']!=dialogue[0]['text'] or dialogue[0]['speaker']!=ch['speaker']:raise ValueError('first dialogue line mismatch')
    # Best-effort textual isolation; editor should review idiomatic false positives.
    corpus=' '.join([ch['text']]+[l['text'] for l in dialogue]).lower()
    if ch['speaker']=='polly' and re.search(r'\b(jos[eé]|michael|fritz|pierre)\b',corpus):raise ValueError('Polly cannot reference other birds')
    if ch['speaker']!='polly' and re.search(r'\bpolly\b',corpus):raise ValueError('main birds cannot reference Polly')
    if ch.get('trigger_phrases') and (ch['speaker']!='polly' or not isinstance(ch['trigger_phrases'],list)):
        raise ValueError('invalid trigger_phrases')
    return ch

def import_file(db,path):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    entries=payload['chirps']
    if not isinstance(entries,list):raise ValueError('chirps must be array')
    seen=set(); validated=[]
    for ch in entries:
        validate(ch)
        if ch['id'] in seen:raise ValueError('duplicate ID within import: '+ch['id'])
        seen.add(ch['id']);validated.append(ch)
    # Transaction all or nothing; update existing IDs but preserve play history.
    with db:
        for ch in validated:
            db.execute('INSERT INTO chirps(id,family_id,speaker,body,enabled) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET family_id=excluded.family_id,speaker=excluded.speaker,body=excluded.body,enabled=excluded.enabled',
                       (ch['id'],ch['family_id'],ch['speaker'],json.dumps(ch,ensure_ascii=False),int(ch.get('enabled',True))))
    return len(validated)

def select(db, speaker, tags, listeners, session, cooldown_hours=1, seed=None):
    if speaker not in BIRDS:raise ValueError('select a named bird')
    tags=set(tags); listeners=set(listeners)
    now=time.time(); rng=random.Random(seed)
    candidates=[]
    for row in db.execute('SELECT body FROM chirps WHERE enabled=1 AND (speaker=? OR speaker=?)', (speaker,'any' if speaker!='polly' else '__never__')):
        ch=json.loads(row['body'])
        required=set(ch['required_tags']);excluded=set(ch['excluded_tags'])
        if not required<=tags or excluded&tags:continue
        if ch['audience']=='adults' and 'adult_mode' not in tags:continue
        # global cooldown by family. also exclude any session listener ever heard family.
        if db.execute('SELECT 1 FROM plays WHERE family_id=? AND played_at>=? LIMIT 1',(ch['family_id'],now-cooldown_hours*3600)).fetchone():continue
        if listeners:
            q=','.join('?'*len(listeners))
            if db.execute('SELECT 1 FROM plays p JOIN listeners l ON l.play_id=p.id WHERE p.family_id=? AND l.listener_id IN ('+q+') LIMIT 1',(ch['family_id'],*listeners)).fetchone():continue
        # session history protects same crowd when no reliable listener IDs.
        if db.execute('SELECT 1 FROM plays WHERE family_id=? AND session_id=? LIMIT 1',(ch['family_id'],session)).fetchone():continue
        score=max(0.001,float(ch.get('weight',1)))*(1+0.5*len(set(ch['optional_tags'])&tags))
        candidates.append((ch,score))
    if not candidates:return None
    items,weights=zip(*candidates)
    return rng.choices(items,weights=weights,k=1)[0]

def record(db,ch,session,listeners):
    with db:
        cur=db.execute('INSERT INTO plays(chirp_id,family_id,played_at,session_id) VALUES(?,?,?,?)',(ch['id'],ch['family_id'],time.time(),session))
        db.executemany('INSERT INTO listeners(play_id,listener_id) VALUES(?,?)',[(cur.lastrowid,p) for p in set(listeners)])

def synth(db,ch,url,play=False):
    # Baked cache survives service restarts and keeps audio aligned with cue JSON.
    texts=[(line['speaker'],line['text']) for line in ch.get('dialogue',[])] or [(ch['speaker'],ch['text'])]
    output=[]
    for speaker,text in texts:
        key=hashlib.sha256((speaker+'\0'+text+'\0'+url).encode()).hexdigest()
        cached=db.execute('SELECT audio,cues FROM audio_cache WHERE cache_key=?',(key,)).fetchone()
        if cached:
            wav=bytes(cached['audio']); meta=json.loads(cached['cues'])
        else:
            body=json.dumps({'bird':speaker,'text':text,'play':False}).encode()
            req=Request(url+'/api/speech',body,{'Content-Type':'application/json'})
            with urlopen(req,timeout=120) as resp:meta=json.load(resp)
            with urlopen(url+meta['audio'],timeout=30) as resp:wav=resp.read()
            with db:db.execute('INSERT OR REPLACE INTO audio_cache VALUES(?,?,?,?,?)',(key,ch['id'],wav,json.dumps(meta),time.time()))
        if play:
            # Use working system ALSA default; no shell, no nondefault device override.
            subprocess.run(['aplay','-q'],input=wav,check=True)
        output.append({'speaker':speaker,'text':text,'duration':meta.get('duration'),'singing_ranges':meta.get('singing_ranges',[]),'cache_key':key})
    return output

def main():
    p=argparse.ArgumentParser(description='BirdPi chirp library CLI')
    p.add_argument('--db',default='data/chirps.sqlite')
    sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('import');a.add_argument('file')
    a=sub.add_parser('select');a.add_argument('--bird',required=True,choices=sorted(BIRDS));a.add_argument('--tags',default='');a.add_argument('--listeners',default='');a.add_argument('--session',default='demo');a.add_argument('--seed',type=int);a.add_argument('--cooldown-hours',type=float,default=1);a.add_argument('--play',action='store_true');a.add_argument('--tts-url',default='http://127.0.0.1:8081')
    a=sub.add_parser('stats')
    args=p.parse_args();Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    db=connect(args.db)
    if args.action=='import':print(json.dumps({'imported':import_file(db,args.file)}));return
    if args.action=='stats':print(json.dumps({'chirps':db.execute('SELECT COUNT(*) FROM chirps').fetchone()[0],'plays':db.execute('SELECT COUNT(*) FROM plays').fetchone()[0]}));return
    tags=[x.strip() for x in args.tags.split(',') if x.strip()];listeners=[x.strip() for x in args.listeners.split(',') if x.strip()]
    ch=select(db,args.bird,tags,listeners,args.session,args.cooldown_hours,args.seed)
    if not ch:print(json.dumps({'selected':None,'reason':'No eligible chirp; no repeats or applicable tags'}));return
    if args.play:
        cues=synth(db,ch,args.tts_url,play=True)
    else:cues=None
    # Only record after all audio playback succeeds; simulation is non-mutating by default.
    if args.play:record(db,ch,args.session,listeners)
    print(json.dumps({'selected':ch,'audio_cues':cues,'recorded':bool(args.play)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
