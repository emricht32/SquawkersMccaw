#!/usr/bin/env python3
"""Safe routing bridge. Runs on the Polly host. Does not replace BirdPi's existing song playback.

'roast' selects and optionally performs Polly only: audio on Polly's own LMS player
(or local ALSA fallback) with beak GPIO on this host.
In 4-bird mode the LMS performance gate keeps Polly and José's songs exclusive.
'song-route' returns a routing plan only; this adapter does NOT start songs.
"""
import argparse
import json
import fcntl
from pathlib import Path
from birdpi_roles import route, validate_comedy, RoutingError
from lms_gate import build_gate, make_client, GateUnavailable
from polly_performer import PollyPerformer, AplaySink, LmsSink
import chirp_engine

BASE_DIR = Path(__file__).resolve().parent


def default_config_path():
    """Per-device config written by pi5_setup.sh wins over the repo default."""
    local=BASE_DIR/'config'/'birdpi_topology.local.json'
    return local if local.exists() else BASE_DIR/'config'/'birdpi_topology.json'


def load_config(path):
    data=json.loads(Path(path).read_text())
    if type(data.get('bird_count')) is not int:
        raise RoutingError('bird_count must be exactly 1, 4, or 5')
    route(data['bird_count'],'polly','comedy')
    return data


def load_pins(cfg):
    pins_file=cfg.get('polly_pins_file')
    if not pins_file:
        return {}
    pins=json.loads((BASE_DIR/pins_file).read_text())
    return {k:pins[k] for k in ('beak','body','lights','light') if k in pins}


def audio_output(cfg):
    output=cfg.get('audio',{}).get('output','lms')
    if output not in ('lms','aplay'):
        raise ValueError('audio.output must be "lms" or "aplay"')
    return output


def build_sink(cfg):
    """Return (sink, polly_player_id or None)."""
    if audio_output(cfg)=='aplay':
        return AplaySink(),None
    lms_cfg=cfg.get('lms',{})
    client=make_client(lms_cfg)
    name=lms_cfg.get('polly_player','birdpi-polly')
    player=client.find_player(name)
    if not player or str(player.get('connected',0))!='1':
        raise GateUnavailable(f'Polly LMS player {name!r} is not registered/connected on {client.host}')
    audio=cfg.get('audio',{})
    sink=LmsSink(client,player['playerid'],client.local_ip(),
                 port=int(audio.get('serve_port',0)),
                 start_timeout_s=float(audio.get('lms_start_timeout_s',8.0)))
    return sink,player['playerid']


def build_performer(cfg, sink):
    beak=cfg.get('beak',{})
    return PollyPerformer(load_pins(cfg),sink,
                          audio_latency_s=float(beak.get('audio_latency_s',0.0)),
                          max_open_s=float(beak.get('max_open_s',0.4)),
                          min_closed_s=float(beak.get('min_closed_s',0.06)))


def roast(count, db_path, tags, listeners, session, tts_url, play=False, gate=None, performer=None,
          max_wait_s=0.0):
    target=route(count,'polly','comedy')
    tagset={s.strip() for s in tags.split(',') if s.strip()}
    # Note: adult_mode and a challenge are OPERATOR-provided, not auto-enabled here.
    if 'adult_mode' not in tagset or not tagset.intersection({'direct_insult','roast_request','roast_challenge'}):
        raise RoutingError('Roasts require explicit adult_mode and a human challenge/request tag')
    db=chirp_engine.connect(db_path)
    ch=chirp_engine.select(db, 'polly',tagset, listeners, session)
    if ch is None:
        return {'selected': None, 'route':vars(target),'recorded':False}
    validate_comedy(ch,count)
    if not play:
        return {'selected':ch,'route':vars(target),'audio_cues':None,'recorded':False,'played':False}
    # Synthesize before taking the gate so a slow Piper call never holds the shared bird.
    wav,meta,key=chirp_engine.render(db,'polly',ch['text'],tts_url,ch['id'])
    cues={'duration':meta.get('duration'),'singing_ranges':meta.get('singing_ranges',[]),
          'voice_model':meta.get('voice_model'),'speaker_id':meta.get('speaker_id'),'cache_key':key}
    result={'selected':ch,'route':vars(target),'audio_cues':cues,'recorded':False,'played':False,
            'gate':gate.kind}
    # Serializes Polly performances from separate processes on this host.
    lock_path=Path('data/birdpi-main-performance.lock')
    lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        if not gate.acquire(max_wait_s):
            result['reason']='song_playing'
            return result
        try:
            perf=performer.perform(wav,cues['singing_ranges'],cues['duration'])
        finally:
            gate.release()
    result['motor_output']=perf['beak']
    result['played']=perf['played']
    if perf.get('error'):
        result['error']=perf['error']
    if perf['played']:
        chirp_engine.record(db,ch,session,listeners)
        result['recorded']=True
    return result


def play_roast(cfg, db_path, tags, listeners, session, tts_url):
    count=cfg['bird_count']
    sink,polly_id=build_sink(cfg)
    gate=build_gate(count,cfg.get('lms'),exclude_ids=[polly_id] if polly_id else [])
    performer=build_performer(cfg,sink)
    return roast(count,db_path,tags,listeners,session,tts_url,True,gate,performer,
                 float(cfg.get('queue',{}).get('polly_max_wait_s',300)))


def main():
    p=argparse.ArgumentParser(description='BirdPi v10 role/topology bridge')
    p.add_argument('--config',default=str(default_config_path()))
    p.add_argument('--db',default='data/chirps.sqlite')
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('status')
    sub.add_parser('song-route')
    a=sub.add_parser('roast');a.add_argument('--tags',required=True);a.add_argument('--listeners',default='');a.add_argument('--session',default='demo');a.add_argument('--play',action='store_true');a.add_argument('--tts-url',default='http://127.0.0.1:8081')
    args=p.parse_args()
    try:
        cfg=load_config(args.config)
        count=cfg['bird_count']
        if args.action=='status':
            result={'bird_count':count,'mode':route(count,'polly','comedy').mode,'comedy':vars(route(count,'polly','comedy')),
                    'singing':vars(route(count,'jose','sing')) if count>1 else None,
                    'gate':build_gate(count,cfg.get('lms')).kind,
                    'audio_output':audio_output(cfg),
                    'polly_player':cfg.get('lms',{}).get('polly_player','birdpi-polly'),
                    'polly_pins':load_pins(cfg),
                    'note':'Only Polly does comedy, only José sings'}
        elif args.action=='song-route':
            result={'route':vars(route(count,'jose','sing')),'dispatched':False,
                    'note':'Pass this route to the existing BirdPi song scheduler; bridge does not invoke it'}
        else:
            Path(args.db).parent.mkdir(parents=True,exist_ok=True)
            listeners=[s.strip() for s in args.listeners.split(',') if s.strip()]
            if args.play:
                result=play_roast(cfg,args.db,args.tags,listeners,args.session,args.tts_url)
            else:
                result=roast(count,args.db,args.tags,listeners,args.session,args.tts_url)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (RoutingError,GateUnavailable,ValueError,OSError) as exc:
        p.exit(2,'Error: '+str(exc)+'\n')

if __name__=='__main__':main()
