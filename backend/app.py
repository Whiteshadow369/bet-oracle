import os, asyncio, json, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('ODDS_API_KEY')
SPORT = os.getenv('SPORT', 'soccer_epl')
POLL_INTERVAL = float(os.getenv('POLL_INTERVAL', '5'))

app = FastAPI(title='Bet-Oracle Live MVP')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

odds_store: Dict[str, Any] = {}
signals_store: Dict[str, Any] = {}
clients: List[WebSocket] = []

async def broadcast(message: dict):
    living = []
    for ws in clients:
        try:
            await ws.send_text(json.dumps(message))
            living.append(ws)
        except Exception:
            pass
    clients[:] = living

@app.get('/health')
async def health():
    return {'status':'ok', 'ts': time.time()}

@app.get('/odds')
async def get_odds():
    return {'status':'success', 'data': list(odds_store.values()), 'ts': time.time()}

@app.post('/predict')
async def predict(request: Request):
    body = await request.json()
    seq = body.get('sequence', [])
    if not isinstance(seq, list):
        return JSONResponse({'status':'error','message':"'sequence' must be list"}, status_code=400)
    res = compute_prediction_from_sequence(seq)
    return {'status':'success', 'prediction': res['prediction'], 'confidence': res['confidence'], 'reason': res['reason']}

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        try:
            clients.remove(ws)
        except ValueError:
            pass

def compute_prediction_from_sequence(seq):
    nums = [float(x) for x in seq] if seq else []
    n = len(nums)
    import statistics
    if n == 0:
        return {'prediction': None, 'confidence': 0.0, 'reason':'empty'}
    if n < 3:
        med = float(statistics.median(nums))
        return {'prediction': med + 1.0, 'confidence': 0.4, 'reason':'short seq'}
    mean = sum(nums)/n
    med = float(statistics.median(nums))
    try:
        mode = float(statistics.mode(nums)); has_mode = True
    except Exception:
        mode = med; has_mode = False
    slope = (nums[-1] - nums[0]) / max(1, (n-1))
    trend_pred = nums[-1] + slope
    weight_recent = 0.6; weight_trend = 0.3; weight_mode = 0.1 if has_mode else 0.0
    pred = (weight_recent * nums[-1]) + (weight_trend * trend_pred) + (weight_mode * mode)
    variance = statistics.pvariance(nums) if n > 1 else 0.0
    conf = max(0.05, min(0.95, 1.0 / (1.0 + variance) * (0.5 + min(0.5, n/20))))
    return {'prediction': pred, 'confidence': round(conf,3), 'reason':'heuristic'}

async def fetch_odds_once(client: httpx.AsyncClient):
    global odds_store, signals_store
    if not API_KEY:
        demo = [
            {'match_id':'m1','bookmaker':'1XBET','match':'Man City vs Arsenal','odds':{'home':2.1,'draw':3.2,'away':3.8}, 'ts': time.time()},
            {'match_id':'m2','bookmaker':'Betway','match':'Real vs Barca','odds':{'home':1.9,'draw':3.6,'away':4.2}, 'ts': time.time()}
        ]
        for d in demo:
            odds_store[d['match_id']] = d
            if d['odds']['home'] < 2.0:
                signal = {'match_id': d['match_id'], 'market':'1X2', 'side':'home', 'confidence':0.6, 'ts': time.time()}
                signals_store[d['match_id']] = signal
        await broadcast({'type':'odds_update','odds': list(odds_store.values()), 'signals': list(signals_store.values())})
        return
    try:
        url = f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds/?regions=eu&markets=spreads,ou,1x2&oddsFormat=decimal&apiKey={API_KEY}'
        resp = await client.get(url, timeout=20.0)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                match_id = item.get('id') or f"{item.get('sport_key')}_{item.get('commence_time')}"
                normalized = {'match_id': match_id, 'bookmaker': item.get('bookmakers',[{}])[0].get('title','unknown'),
                              'match': item.get('home_team','') + ' vs ' + item.get('away_team',''), 'odds': {}, 'ts': time.time()}
                try:
                    bk = item.get('bookmakers',[{}])[0]
                    if bk:
                        markets = bk.get('markets', [])
                        for m in markets:
                            if m.get('key') == 'h2h' or m.get('key') == '1x2':
                                outcomes = m.get('outcomes', [])
                                for o in outcomes:
                                    nm = o.get('name','').lower()
                                    price = o.get('price',None)
                                    if 'home' in nm or o.get('name','').lower() == item.get('home_team','').lower():
                                        normalized['odds']['home'] = price
                                    elif 'away' in nm or o.get('name','').lower() == item.get('away_team','').lower():
                                        normalized['odds']['away'] = price
                                    elif 'draw' in nm:
                                        normalized['odds']['draw'] = price
                except Exception:
                    pass
                odds_store[match_id] = normalized
                if normalized['odds'].get('home') and normalized['odds']['home'] < 2.0:
                    signals_store[match_id] = {'match_id': match_id, 'market':'1X2', 'side':'home', 'confidence':0.6, 'ts': time.time()}
            await broadcast({'type':'odds_update','odds': list(odds_store.values()), 'signals': list(signals_store.values())})
    except Exception as e:
        print('fetch error', e)

async def ingest_loop():
    async with httpx.AsyncClient() as client:
        while True:
            await fetch_odds_once(client)
            await asyncio.sleep(POLL_INTERVAL)

@app.on_event('startup')
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.create_task(ingest_loop())
