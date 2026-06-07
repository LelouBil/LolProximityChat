/** @type {MediaStream | null} */
let localStream;

/** @type {WebSocket | null} */
let signaling

/** @type {string | null} */
let ownPlayer

async function createLocalStream() {
    localStream = await navigator.mediaDevices.getUserMedia({audio: true})
}

/** @type {Map<string,PlayerStream>} */
const playerStreams = new Map();

class PlayerStream {
    /** @type {RTCPeerConnection} */
    connection

    /** @type {string} */
    targetPlayerName

    /** @type {(MediaStream) => void} */
    onStream


    #createConnection() {
        const pc = new RTCPeerConnection(
            {
                iceServers: [
                    {
                        urls: "stun:stun.l.google.com:19302"
                    }
                ]
            }
        );
        pc.onicecandidate = e => {
            const message = {
                type: 'candidate',
                source: ownPlayer,
                target: this.targetPlayerName,
                candidate: null,
            };
            if (e.candidate) {
                message.candidate = e.candidate.candidate;
                message.sdpMid = e.candidate.sdpMid;
                message.sdpMLineIndex = e.candidate.sdpMLineIndex;
            }
            signaling.send(JSON.stringify(message));
        };
        pc.ontrack = e => {
            if (this.onStream) {
                this.onStream(e.streams[0]);
            }
        }
        localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
        this.connection = pc;
    }


    /**
     * @param {string} targetPlayerName
     * @param {boolean} start
     */
    constructor(targetPlayerName, start) {
        this.targetPlayerName = targetPlayerName;
        this.#createConnection()
        if (start) {
            this.connection.createOffer().then(async offer => {
                    signaling.send(JSON.stringify({
                        type: 'offer',
                        sdp: offer.sdp,
                        source: ownPlayer,
                        target: this.targetPlayerName
                    }));
                    await this.connection.setLocalDescription(offer);
                }
            )
        }
    }

    async handleOffer(offer) {
        console.assert(offer.type === 'offer', 'offer is not of type offer');
        console.assert(offer.target === ownPlayer, 'offer is not from own player')
        console.assert(
            offer.source === this.targetPlayerName,
            `offer ${offer.source} is not from the expected player ${this.targetPlayerName}`
        )
        if (this.connection.connectionState === "connected") {
            this.connection.close()
            this.#createConnection()
        }
        await this.connection.setRemoteDescription(offer);
        const answer = await this.connection.createAnswer();
        signaling.send(JSON.stringify({
            type: 'answer',
            source: ownPlayer,
            target: this.targetPlayerName,
            sdp: answer.sdp
        }));
        await this.connection.setLocalDescription(answer);
    }

    async handleAnswer(answer) {
        console.assert(answer.type === 'answer', 'answer is not of type answer');
        console.assert(answer.target === ownPlayer, 'answer is not from own player')
        console.assert(
            answer.source === this.targetPlayerName,
            'answer is not from the expected player'
        )
        await this.connection.setRemoteDescription(answer);
    }

    async handleCandidate(candidate) {
        console.assert(candidate.type === 'candidate', 'candidate is not of type candidate');
        console.assert(candidate.target === ownPlayer, 'candidate is not from own player')
        console.assert(
            candidate.source === this.targetPlayerName,
            'candidate is not from the expected player'
        )
        if (!candidate.candidate) {
            await this.connection.addIceCandidate(null);
        } else {
            await this.connection.addIceCandidate(candidate);
        }
    }
}


/** @param {WebSocket} signalingws
 * @param {string} ownName */
export async function createSignaling(signalingws, ownName) {
    signaling = signalingws;
    ownPlayer = ownName
    await createLocalStream()

    signaling.addEventListener("message", async e => {
        if (!localStream) {
            return;
        }
        const data = JSON.parse(e.data);
        if (data.target !== ownPlayer) return;
        switch (data.type) {
            case 'offer':
                console.log("received offer")
                let ps = getPlayerStream(data.source, false);
                await ps.handleOffer(data);
                break;
            case 'answer':
                console.log("received answer")
                let pstream = getPlayerStream(data.source, false);
                await pstream.handleAnswer(data);
                break;
            case 'candidate':
                console.log("received candidate")
                let pstream2 = getPlayerStream(data.source, false);
                await pstream2.handleCandidate(data);
                break;
            default:
                break;
        }
    });

}

/** @param {string} name
 * @param {boolean} start */
export function getPlayerStream(name, start) {
    if (signaling === null) throw new Error(
        "Signaling not initialized. Call createSignaling first."
    )
    let stream = playerStreams.get(name);
    if (!stream) {
        stream = new PlayerStream(name, start);
        playerStreams.set(name, stream);
    }
    return stream;
}
