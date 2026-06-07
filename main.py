import asyncio
import time
from dataclasses import dataclass
from typing import NewType, Any

import aiohttp
import lcu_driver

ChampionName = NewType('ChampionName', str)
GameName = NewType('GameName', str)
GameID = NewType('GameID', str)


@dataclass
class Vector3:
    x: float
    y: float
    z: float


@dataclass
class LeaguePlayer:
    name: GameName
    champion: ChampionName


class LCUConnector():
    connection: aiohttp.ClientSession

    def __init__(self, connection: aiohttp.ClientSession):
        self.connection = connection

    async def get_game_id(self) -> GameID:
        resp = await self.connection.request('get', '/lol-gameflow/v1/session')
        if resp.status != 200:
            raise Exception(f"LCU API request failed, status code: {resp.status}")
        data = await resp.json()
        game_data = data.get("gameData")
        if game_data is None:
            raise Exception(f"gameData not found in LCU response: {data}")
        game_id = game_data.get("gameId")
        if game_id is None:
            raise Exception(f"gameId not found in LCU response: {data}")
        return GameID(str(game_id))


class LiveGameConnector():
    _client: aiohttp.ClientSession
    BASE_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
    last_data: dict[str, Any] = None

    def __init__(self, client: aiohttp.ClientSession):
        self._client = client

    async def _request(self) -> dict[str, Any]:
        async with self._client.get(self.BASE_URL, ssl=False) as resp:
            if resp.status != 200:
                raise Exception(f"Live Game API request failed, status code: {resp.status}")
            return await resp.json()

    async def start(self):
        try:
            await self._request()
        except Exception as e:
            raise Exception(f"Live Game API not ready: {e}")
        asyncio.create_task(self._poll_loop())

    async def _poll_loop(self):
        while True:
            try:
                self.last_data = await self._request()
            except Exception as e:
                print(f"Live Game API request failed: {e}")

    def get_players(self):
        if self.last_data is None:
            return []
        all_players = self.last_data.get("allPlayers", [])

        def map_player(p: dict[str, Any]) -> LeaguePlayer:
            summ: str | None = p.get("riotIdGameName")
            if summ is None:
                raise Exception(f"Summoner name not found in player data: {p}")
            champ: str | None = p.get("championName")
            if champ is None:
                raise Exception(f"Champion name not found in player data: {p}")
            return LeaguePlayer(name=GameName(summ), champion=ChampionName(champ))

        return [map_player(p) for p in all_players]

    def get_dead_players(self) -> list[GameName]:
        if self.last_data is None:
            return []
        all_players = self.last_data.get("allPlayers", [])
        return [GameName(p.get("riotIdGameName")) for p in all_players if p.get("isDead", False)]


class ReplayConnector():
    _client: aiohttp.ClientSession
    BASE_URL = "https://127.0.0.1:2999/replay/render"

    def __init__(self, client: aiohttp.ClientSession):
        self._client = client

    async def get_position(self, sum: GameName) -> Vector3:
        payload = {"selectionName": sum, "cameraAttached": True, "cameraMode": "fps",
                   "selectionOffset": {'x': 0.0, 'y': 0.0, 'z': 0.0}}
        async with self._client.post(self.BASE_URL, json=payload, ssl=False) as resp:
            if resp.status != 200:
                raise Exception(f"Replay API post request failed, status code: {resp.status}")
        async with self._client.get(self.BASE_URL, ssl=False) as resp:
            if resp.status != 200:
                raise Exception(f"Replay API get request failed, status code: {resp.status}")
            data = await resp.json()
            offset = data.get("cameraPosition")
            if offset is None:
                raise Exception(f"cameraPosition not found in replay response: {data}")
            return Vector3(x=offset["x"], y=offset["y"], z=offset["z"])

    async def ready(self):
        async with self._client.get(self.BASE_URL, ssl=False) as resp:
            if resp.status != 200:
                raise Exception(f"Replay API not ready, status code: {resp.status}")
            print(await resp.json())


class PositionsExtractor():
    _client: aiohttp.ClientSession
    _replay_connector: ReplayConnector
    _live_connector: LiveGameConnector
    _lcu_connector: LCUConnector
    _ws: aiohttp.ClientWebSocketResponse

    WS_URL = "ws://localhost:8765/ws"

    positions: dict[GameName, Vector3] = {}
    poll_task: asyncio.Task | None = None

    def __init__(self, connector: aiohttp.ClientSession):
        self._client = aiohttp.ClientSession()
        self._lcu_connector = LCUConnector(connector)
        self._replay_connector = ReplayConnector(self._client)
        self._live_connector = LiveGameConnector(self._client)

    async def start(self):
        await self._live_connector.start()
        await self._replay_connector.ready()
        self._ws = await self._client.ws_connect(self.WS_URL)
        # game_id = await self._lcu_connector.get_game_id()
        game_id = "0" #TODO testing
        print(f"Connected to WebSocket server, joining game {game_id}...")
        await self._ws.send_json({
            "type": "join",
            "game_id": game_id
        })
        self.poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self):
        while True:
            try:
                players = self._live_connector.get_players()
                res: dict[GameName, Vector3] = {}
                for p in players:
                    pos = await self._replay_connector.get_position(p.name)
                    res[p.name] = pos  # print(f"Player {p.name} ({p.champion}) position: {pos}")
                self.positions = res
                payload = {
                    "type": "positions",
                    "players": [
                        {
                            "id": str(p.name),
                            "champion": str(p.champion),
                            "dead": p.name in self._live_connector.get_dead_players(),
                            "pos": {
                                "x": res[p.name].x,
                                "y": res[p.name].y,
                                "z": res[p.name].z,
                            }
                        }
                        for p in players
                    ]
                }
                await self._ws.send_json(payload)
            except Exception as e:
                print(f"Error in poll loop: {e}")
            finally:
                await asyncio.sleep(0)

    async def stop(self):
        if self.poll_task:
            self.poll_task.cancel()
        await self._client.close()


connector = lcu_driver.Connector()


@connector.ready
async def main(connection):
    print("Starting spectator tracker...")
    extractor = PositionsExtractor(connection)

    try:
        await extractor.start()
        while True:
            await asyncio.sleep(0)
    except KeyboardInterrupt:
        print("exiting")
    finally:
        await extractor.stop()


if __name__ == "__main__":
    connector.start()
