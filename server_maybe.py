import json
from collections import defaultdict
from aiohttp import web

games = defaultdict(list)  # game_id -> ws set
ws_game = {}  # ws -> game_id


async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    game_id = None

    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue

            data = json.loads(msg.data)
            msg_type = data.get("type")

            #################################################
            # JOIN GAME
            #################################################
            if msg_type == "join":
                game_id = data["game_id"]

                games[game_id].append(ws)
                ws_game[ws] = game_id

                await ws.send_json({
                    "type": "joined",
                    "game_id": game_id,
                    "peers": len(games[game_id]) - 1
                })

                print(f"[JOIN] {game_id} peers={len(games[game_id])}")
                continue

            #################################################
            # POSITION BROADCAST
            #################################################

            if msg_type == "positions":
                if game_id is None:
                    print("Error: Received positions message before join")
                    continue

                dead = []

                for peer in games[game_id]:
                    if peer is ws:
                        continue

                    try:
                        await peer.send_json(data)

                    except Exception as e:
                        print(f"Peer disconnected during send: {e}")
                        dead.append(peer)

                for d in dead:
                    games[game_id].remove(d)

            # WebRTC
            if msg_type == "offer" or msg_type == "candidate" or msg_type == "answer":
                if game_id is None:
                    print("Error: Received offer/candidate message before join")
                    continue

                dead = []
                print("rebroadcasting offer/candidate to peers")
                for peer in games[game_id]:
                    if peer is ws:
                        continue
                    try:
                        await peer.send_json(data)
                    except Exception as e:
                        print(f"Peer disconnected during send: {e}")
                        dead.append(peer)

                for d in dead:
                    games[game_id].remove(d)



    finally:

        if game_id and ws in games[game_id]:
            games[game_id].remove(ws)

        ws_game.pop(ws, None)

        print(f"[LEAVE] {game_id}")

    return ws


async def root_handler(request):
    return web.HTTPFound('/index.html')

app = web.Application()
app.router.add_get("/ws", ws_handler)
app.router.add_route('*','/',root_handler)
app.router.add_static("/", "./static",show_index=True)

web.run_app(app, host="127.0.0.1", port=8765)