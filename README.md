# League of Legends Proximity chat

# Requirements
- One league of legends instance running as spectator
- A custom game, with spectator delay disabled


This is mostly intended towards developers, at least people that can run Python scripts and expose a page over HTTPs
from their computer. If someone can show me a way to not need websockets or have a public websocket server that I don't
have to manage, maybe this can get more user-friendly.

# Tutorial



The person running the spectating instance needs to run the `main.py` script.

If they do not want to see lots of flickering, they should also not look at the game window, it will flicker a lot.

Maybe mute it as well since sound will also flicker.


Then, this person should use something like cloudflare private tunnels or ngrok, to expose the address shown in their 
terminal to other players.

Other players can then join the voice chat by going to the URL given to them, selecting their name at the bottom left 
and pressing "start", they should accept the request from their browser to use the microphone.

