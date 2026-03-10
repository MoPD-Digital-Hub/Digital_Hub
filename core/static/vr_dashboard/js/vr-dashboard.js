(function () {
    const dataNode = document.getElementById("vr-dashboard-data");
    const enterVrButton = document.getElementById("enter-vr-button");
    const previewButton = document.getElementById("focus-vr-preview");
    const statusNode = document.getElementById("xr-status");
    const stageNode = document.getElementById("vr-stage");
    const dashboardData = dataNode ? JSON.parse(dataNode.textContent) : {
        kpis: [],
        menu: [],
        notifications: [],
        charts: [],
    };

    let aframeReady = false;
    let sceneBuilt = false;

    async function checkXRSupport() {
        if (!navigator.xr) {
            statusNode.textContent = "WebXR unavailable in this browser. 2D dashboard remains active.";
            enterVrButton.disabled = true;
            return;
        }

        try {
            const supported = await navigator.xr.isSessionSupported("immersive-vr");
            statusNode.textContent = supported
                ? "WebXR immersive VR is available. Quest, Vive, and Chrome-compatible headsets can enter XR."
                : "WebXR detected, but immersive VR is not available on this device. Desktop 3D preview remains available.";
            enterVrButton.disabled = !supported;
        } catch (error) {
            statusNode.textContent = "WebXR check failed. Standard dashboard mode is still available.";
            enterVrButton.disabled = true;
            console.error(error);
        }
    }

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const existing = document.querySelector(`script[src="${src}"]`);
            if (existing) {
                if (existing.dataset.loaded === "true") {
                    resolve();
                    return;
                }

                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
                return;
            }

            const script = document.createElement("script");
            script.src = src;
            script.async = true;
            script.addEventListener("load", () => {
                script.dataset.loaded = "true";
                resolve();
            }, { once: true });
            script.addEventListener("error", reject, { once: true });
            document.head.appendChild(script);
        });
    }

    async function ensureAFrame() {
        if (aframeReady) {
            return;
        }

        await loadScript("https://aframe.io/releases/1.7.0/aframe.min.js");
        registerComponents();
        aframeReady = true;
    }

    function registerComponents() {
        if (!window.AFRAME || AFRAME.components["draggable-panel"]) {
            return;
        }

        AFRAME.registerComponent("draggable-panel", {
            schema: {
                distance: { default: 0.7 },
            },
            init: function () {
                this.isGrabbed = false;
                this.grabber = null;
                this.offset = new AFRAME.THREE.Vector3();
                this.onGrabStart = this.onGrabStart.bind(this);
                this.onGrabEnd = this.onGrabEnd.bind(this);
                this.el.classList.add("interactive");
                this.el.addEventListener("grab-start", this.onGrabStart);
                this.el.addEventListener("grab-end", this.onGrabEnd);
            },
            tick: function () {
                if (!this.isGrabbed || !this.grabber) {
                    return;
                }

                const direction = new AFRAME.THREE.Vector3();
                const worldTarget = new AFRAME.THREE.Vector3();
                this.grabber.object3D.getWorldDirection(direction);
                this.grabber.object3D.getWorldPosition(worldTarget);
                worldTarget.add(direction.multiplyScalar(-this.data.distance));
                const localTarget = this.el.object3D.parent.worldToLocal(worldTarget);
                localTarget.add(this.offset);
                this.el.object3D.position.lerp(localTarget, 0.3);
            },
            onGrabStart: function (event) {
                const hand = event.detail && event.detail.hand;
                if (!hand) {
                    return;
                }

                this.isGrabbed = true;
                this.grabber = hand;
                const handWorld = new AFRAME.THREE.Vector3();
                const panelWorld = new AFRAME.THREE.Vector3();
                hand.object3D.getWorldPosition(handWorld);
                this.el.object3D.getWorldPosition(panelWorld);
                this.offset.copy(panelWorld.sub(handWorld).multiplyScalar(0.18));
            },
            onGrabEnd: function () {
                this.isGrabbed = false;
                this.grabber = null;
                this.offset.set(0, 0, 0);
            },
        });

        AFRAME.registerComponent("xr-pointer", {
            init: function () {
                this.grabbedEl = null;
                this.startGrab = this.startGrab.bind(this);
                this.endGrab = this.endGrab.bind(this);
                this.el.addEventListener("triggerdown", this.startGrab);
                this.el.addEventListener("triggerup", this.endGrab);
                this.el.addEventListener("pinchstarted", this.startGrab);
                this.el.addEventListener("pinchended", this.endGrab);
            },
            startGrab: function () {
                const raycaster = this.el.components.raycaster;
                if (!raycaster || !raycaster.intersections.length) {
                    return;
                }

                const hit = raycaster.intersections[0].object.el;
                if (!hit || !hit.components["draggable-panel"]) {
                    return;
                }

                this.grabbedEl = hit;
                hit.emit("grab-start", { hand: this.el });
            },
            endGrab: function () {
                if (!this.grabbedEl) {
                    return;
                }

                this.grabbedEl.emit("grab-end", { hand: this.el });
                this.grabbedEl = null;
            },
        });

        AFRAME.registerComponent("menu-action", {
            schema: { label: { default: "" } },
            init: function () {
                this.defaultColor = "#10202f";
                this.hoverColor = "#1d6fa2";
                this.el.addEventListener("mouseenter", () => {
                    this.el.setAttribute("material", "color", this.hoverColor);
                });
                this.el.addEventListener("mouseleave", () => {
                    this.el.setAttribute("material", "color", this.defaultColor);
                });
                this.el.addEventListener("click", () => {
                    const title = document.querySelector("#active-menu-title");
                    if (title) {
                        title.setAttribute("value", this.data.label);
                    }
                });
            },
        });

        AFRAME.registerComponent("gesture-scroll", {
            init: function () {
                this.target = null;
                this.lastY = null;
                this.el.addEventListener("pinchstarted", (event) => {
                    this.target = document.querySelector("#notifications-rig");
                    this.lastY = event.detail.position.y;
                });
                this.el.addEventListener("pinchmoved", (event) => {
                    if (!this.target || this.lastY === null) {
                        return;
                    }

                    const delta = event.detail.position.y - this.lastY;
                    this.lastY = event.detail.position.y;
                    const position = this.target.getAttribute("position");
                    const nextY = Math.min(1.85, Math.max(0.75, position.y + delta * 1.45));
                    this.target.setAttribute("position", `${position.x} ${nextY.toFixed(3)} ${position.z}`);
                });
                this.el.addEventListener("pinchended", () => {
                    this.lastY = null;
                });
            },
        });

        AFRAME.registerComponent("hologram-pulse", {
            tick: function (time) {
                const opacity = 0.48 + Math.sin(time / 280) * 0.14;
                this.el.setAttribute("material", "opacity", opacity);
            },
        });
    }

    function buildSceneMarkup() {
        const kpiCards = dashboardData.kpis.map((card) => `
            <a-entity class="interactive dashboard-panel"
                geometry="primitive: box; width: 1.05; height: 0.62; depth: 0.06"
                material="color: #0c1622; metalness: 0.15; roughness: 0.24; opacity: 0.94"
                position="${card.position}"
                draggable-panel
                shadow="cast: true; receive: true">
                <a-text value="${card.label}" width="1.2" color="#8eb3c6" position="-0.42 0.18 0.04"></a-text>
                <a-text value="${card.value}" width="2.1" color="#f0fbff" position="-0.42 -0.02 0.04"></a-text>
                <a-text value="${card.delta}" width="1.25" color="#5de4c7" position="-0.42 -0.2 0.04"></a-text>
            </a-entity>
        `).join("");

        const chartBars = dashboardData.charts.map((value, index) => `
            <a-box
                position="${-0.75 + index * 0.3} ${-0.48 + value * 0.7} 0.06"
                width="0.18"
                depth="0.12"
                height="${Math.max(0.2, value * 1.4)}"
                color="${index % 2 === 0 ? "#5de4c7" : "#7cb8ff"}"
                shadow="cast: true">
            </a-box>
        `).join("");

        const menuItems = dashboardData.menu.map((item, index) => {
            const angle = -48 + index * 24;
            const radians = angle * (Math.PI / 180);
            const x = Math.sin(radians) * 2.15;
            const z = -3.4 + Math.cos(radians) * 0.45;
            return `
                <a-entity
                    geometry="primitive: box; width: 0.72; height: 0.22; depth: 0.06"
                    material="color: #10202f; opacity: 0.95"
                    position="${x.toFixed(2)} 0.9 ${z.toFixed(2)}"
                    rotation="0 ${-angle} 0"
                    class="interactive"
                    menu-action="label: ${item}">
                    <a-text value="${item}" width="1" align="center" color="#f0fbff" position="0 -0.03 0.04"></a-text>
                </a-entity>
            `;
        }).join("");

        const notifications = dashboardData.notifications.map((item, index) => `
            <a-entity
                geometry="primitive: box; width: 1.4; height: 0.25; depth: 0.04"
                material="color: #10354a; emissive: #1d85aa; emissiveIntensity: 0.14; opacity: 0.72"
                position="0 ${0.32 - index * 0.32} 0"
                hologram-pulse>
                <a-text value="${item}" wrap-count="28" width="1.28" color="#dffaff" position="-0.62 -0.03 0.03"></a-text>
            </a-entity>
        `).join("");

        return `
            <a-scene
                embedded
                renderer="antialias: true; colorManagement: true; physicallyCorrectLights: false; sortObjects: true"
                vr-mode-ui="enabled: false"
                background="color: #04131d">
                <a-assets timeout="10000"></a-assets>

                <a-entity id="workspace-root">
                    <a-plane rotation="-90 0 0" width="24" height="24" color="#07111a" material="roughness: 1"></a-plane>
                    <a-plane position="0 0 -9" width="22" height="10" color="#061420"></a-plane>
                    <a-ring position="0 3.2 -7.8" radius-inner="1.8" radius-outer="1.92" color="#16364a" material="opacity: 0.24"></a-ring>
                    <a-entity light="type: ambient; intensity: 0.8; color: #8db7c7"></a-entity>
                    <a-entity light="type: directional; intensity: 0.55; color: #d9f7ff" position="-1 3 1"></a-entity>
                    <a-entity light="type: point; intensity: 0.85; distance: 12; color: #5de4c7" position="0 2.8 -2.5"></a-entity>

                    ${kpiCards}

                    <a-entity
                        id="analytics-wall"
                        class="interactive"
                        geometry="primitive: box; width: 2.4; height: 1.6; depth: 0.06"
                        material="color: #0d1824; roughness: 0.25"
                        position="0 1.18 -3.15"
                        draggable-panel>
                        <a-text value="Engagement Timeline" width="2.1" color="#f0fbff" position="-1 0.6 0.04"></a-text>
                        <a-text value="interactive 3D chart panel" width="1.5" color="#7ea2b4" position="-1 0.42 0.04"></a-text>
                        ${chartBars}
                    </a-entity>

                    <a-entity
                        id="notifications-rig"
                        class="interactive"
                        position="2.3 1.2 -2.75"
                        draggable-panel>
                        <a-entity geometry="primitive: box; width: 1.6; height: 1.45; depth: 0.05" material="color: #0d1922; opacity: 0.9"></a-entity>
                        <a-text value="Holographic Alerts" width="1.6" color="#f0fbff" position="-0.65 0.55 0.04"></a-text>
                        ${notifications}
                    </a-entity>

                    <a-entity
                        class="interactive"
                        geometry="primitive: box; width: 1.7; height: 1.08; depth: 0.06"
                        material="color: #0d1824; opacity: 0.92"
                        position="-2.35 1.08 -2.75"
                        rotation="0 18 0"
                        draggable-panel>
                        <a-text value="Widget Dock" width="1.7" color="#f0fbff" position="-0.68 0.34 0.04"></a-text>
                        <a-text value="Grab panels to reorganize the workspace." width="1.2" wrap-count="24" color="#b7d3df" position="-0.68 0.06 0.04"></a-text>
                        <a-text value="Pinch with hand tracking to scroll alert stacks." width="1.2" wrap-count="25" color="#7ea2b4" position="-0.68 -0.22 0.04"></a-text>
                    </a-entity>

                    ${menuItems}

                    <a-text id="active-menu-title" value="Overview" width="3" align="center" color="#5de4c7" position="0 2.65 -3.15"></a-text>
                </a-entity>

                <a-entity id="cameraRig" position="0 1.6 0">
                    <a-camera position="0 0 0" look-controls wasd-controls="enabled: true">
                        <a-cursor raycaster="objects: .interactive" fuse="false" material="color: #5de4c7; shader: flat"></a-cursor>
                    </a-camera>
                </a-entity>

                <a-entity
                    id="leftHand"
                    hand-tracking-controls="hand: left; modelStyle: dots"
                    laser-controls="hand: left"
                    raycaster="objects: .interactive"
                    line="color: #5de4c7"
                    xr-pointer
                    gesture-scroll>
                </a-entity>
                <a-entity
                    id="rightHand"
                    hand-tracking-controls="hand: right; modelStyle: dots"
                    laser-controls="hand: right"
                    raycaster="objects: .interactive"
                    line="color: #7cb8ff"
                    xr-pointer>
                </a-entity>
            </a-scene>
        `;
    }

    async function ensureScene(mode) {
        await ensureAFrame();

        if (!sceneBuilt) {
            stageNode.innerHTML = buildSceneMarkup();
            stageNode.dataset.state = "loaded";
            sceneBuilt = true;
        }

        stageNode.scrollIntoView({ behavior: "smooth", block: "center" });

        const sceneEl = stageNode.querySelector("a-scene");
        if (mode === "vr" && sceneEl && sceneEl.enterVR) {
            sceneEl.enterVR();
        }
    }

    enterVrButton.addEventListener("click", async () => {
        enterVrButton.disabled = true;
        statusNode.textContent = "Loading WebXR scene...";
        try {
            await ensureScene("vr");
            statusNode.textContent = "VR scene loaded. Use controllers, hand rays, pinch gestures, and grab interactions.";
        } catch (error) {
            statusNode.textContent = "Unable to load VR scene. Check browser permissions or network access to the A-Frame CDN.";
            console.error(error);
        } finally {
            enterVrButton.disabled = false;
        }
    });

    previewButton.addEventListener("click", async () => {
        previewButton.disabled = true;
        try {
            await ensureScene("preview");
            statusNode.textContent = "3D preview loaded inline. Desktop mode still uses the standard 2D dashboard.";
        } catch (error) {
            statusNode.textContent = "Unable to load 3D preview.";
            console.error(error);
        } finally {
            previewButton.disabled = false;
        }
    });

    checkXRSupport();
})();
