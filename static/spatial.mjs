export class SpatialAudioPlayer {
    /** @type {AudioContext} */
    context
    /** @type {Map<string,PannerNode>} */
    panners
    /** @type {string} */
    name

    /** @type {Map<string,MediaStreamAudioSourceNode>} */
    sources


    /** @param {string[]} players
     * @param {string} ownName
     * @param {number} refDistance
     * @param {number} maxDistance
     * @param {number} rolloffFactor */
    constructor(players, ownName,
                refDistance,
                maxDistance, rolloffFactor) {
        this.name = ownName;
        this.context = new AudioContext();
        this.sources = new Map();
        const panningModel = "HRTF";
        const distanceModel = "linear"
        const panners = new Map()
        for (let name of players) {
            const pannerNode = new PannerNode(this.context, {
                panningModel,
                distanceModel,
                refDistance,
                maxDistance,
                rolloffFactor,
                coneInnerAngle: 360,
                coneOuterAngle: 0,
                coneOuterGain: 0,
            })
            pannerNode.connect(this.context.destination);
            panners.set(name, pannerNode);
        }
        this.panners = panners;
    }

    /** @param {string} name
     * @param {MediaStream} stream*/
    setStream(name, stream) {
        console.log("stream state", {
            active: stream.active,
            tracks: stream.getTracks().map(t => ({
                kind: t.kind,
                readyState: t.readyState,
                muted: t.muted,
                enabled: t.enabled
            }))
        });
        const panner = this.panners.get(name);
        panner.disconnect()
        let mediaStreamAudioSourceNode = this.context
            .createMediaStreamSource(stream);

        this.sources.set(name, mediaStreamAudioSourceNode);
        mediaStreamAudioSourceNode
            .connect(panner)
        panner.connect(this.context.destination);
    }

    /** @param {Map<string,{x:number,y:number,height: number}>} positions */
    positionsUpdated(
        positions
    ) {
        const ownPos = positions.get(this.name);
        // console.log(`Listener (${this.name}):`, ownPos);
        //firefox
        if (navigator.userAgent.toLowerCase().includes('firefox')) {
            this.context.listener.setPosition(ownPos.x, ownPos.y, ownPos.height);

            this.context.listener.setOrientation(0, 1, 0, 0, 0, 1);
        } else {
            this.context.listener.positionX.value = ownPos.x;
            this.context.listener.positionY.value = ownPos.y;
            this.context.listener.positionZ.value = ownPos.height;
        }


        for (const [name, node] of this.panners.entries()) {
            const pos = positions.get(name);
            // console.log(`Panner (${name}):`, pos);
            // node.setPosition(pos.x, pos.y, pos.height);
            node.positionX.value = pos.x;
            node.positionY.value = pos.y;
            node.positionZ.value = pos.height;
        }
    }

    async play() {
        if (this.context.state === "suspended") {
            await this.context.resume();
        }

        // Play or pause track depending on state
        if (playButton.dataset.playing === "false") {
            audioElement.play();
            playButton.dataset.playing = "true";
        } else if (playButton.dataset.playing === "true") {
            audioElement.pause();
            playButton.dataset.playing = "false";
        }
    }

}