import {
  FilesetResolver,
  HandLandmarker,
  PoseLandmarker,
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/+esm";

const VISION_VERSION = "1.0.1";
const VISION_WASM = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VISION_VERSION}/wasm`;
const HAND_MODEL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
const POSE_MODEL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const HOLD_MS = 150;
// Keep these values aligned with src/handyband/drum_gesture.py.
const DRUM = {
  startSpeed: 0.60,
  stopSpeed: 0.20,
  minimumAverageSpeed: 2.00,
  maximumVolumeSpeed: 14.00,
  minimumVolume: 0.10,
  maximumVolume: 0.75,
  volumeExponent: 2.00,
  minimumDistance: 0.20,
  speedSmoothing: 0.45,
  cooldownMs: 500,
};
const STYLE_SAFETY_INTERVALS_MS = {
  Odysseus: { Left: 75_000, Right: 75_000 },
  Piano: { Left: 1_640, Right: 820 },
};
const FINGER_ORDER = ["Thumb", "Index", "Middle", "Ring", "Pinky"];
const FINGER_JOINTS = {
  Thumb: [1, 2, 3, 4],
  Index: [5, 6, 7, 8],
  Middle: [9, 10, 11, 12],
  Ring: [13, 14, 15, 16],
  Pinky: [17, 18, 19, 20],
};
const GESTURE_PATTERNS = new Map([
  ["00000", 0], ["01000", 1], ["01100", 2], ["00111", 3],
  ["01111", 4], ["11111", 5], ["10001", 6], ["11000", 7],
]);
const HAND_CONNECTIONS = [
  [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15],
  [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17],
];

const page = {
  stage: document.querySelector("#stage"),
  cameraButton: document.querySelector("#camera-button"),
  cameraScreen: document.querySelector("#camera-screen"),
  pauseOverlay: document.querySelector("#pause-overlay"),
  fullscreenButton: document.querySelector("#fullscreen-button"),
  channelButtons: document.querySelectorAll("[data-channel]"),
  channelReadout: document.querySelector("#channel-readout"),
  camera: document.querySelector("#camera"),
  overlay: document.querySelector("#landmark-overlay"),
  placeholder: document.querySelector("#camera-placeholder"),
  cameraStatus: document.querySelector("#camera-status"),
  modelStatus: document.querySelector("#model-status"),
  gestureState: document.querySelector("#gesture-state"),
  style: document.querySelector("#style"),
  styleNote: document.querySelector("#style-note"),
};

const audioPaths = {
  drum: asset("HandyBand_Audio/Odysseus/drum.wav"),
  odysseus: Object.fromEntries(
    Array.from({ length: 7 }, (_, index) => [
      index + 1,
      asset(`HandyBand_Audio/Odysseus/od_oboe_${String(index + 1).padStart(2, "0")}.wav`),
    ]),
  ),
  pianoRight: Object.fromEntries(
    Array.from({ length: 6 }, (_, index) => [index + 1, asset(`HandyBand_Audio/Piano/pi_${index + 1}.wav`)]),
  ),
  pianoLeft: Object.fromEntries(
    Array.from({ length: 6 }, (_, index) => [index + 1, asset(`HandyBand_Audio/Piano/lef_${index + 1}.wav`)]),
  ),
};

const state = {
  audio: null,
  stream: null,
  handLandmarker: null,
  poseLandmarker: null,
  modelsPromise: null,
  running: false,
  paused: false,
  animationFrame: null,
  lastVideoTime: -1,
  fingerStates: new Map(["Left", "Right"].map((side) => [side, newFingerState()])),
  drumStates: new Map(["Left", "Right"].map((side) => [side, newDrumState()])),
  pendingDrum: null,
  latestFingerStatuses: [],
  latestDrumStatuses: [],
};

function asset(path) {
  return new URL(`../${path}`, import.meta.url).href;
}

class AudioBank {
  constructor() {
    this.context = null;
    this.buffers = new Map();
    this.loading = null;
  }

  async unlock() {
    this.context ??= new AudioContext();
    if (this.context.state !== "running") {
      await this.context.resume();
    }
    this.loading ??= this.loadAll();
    return this.loading;
  }

  async suspend() {
    if (this.context?.state === "running") await this.context.suspend();
  }

  async loadAll() {
    const entries = [
      ["drum", audioPaths.drum],
      ...Object.entries(audioPaths.odysseus).map(([key, url]) => [`odysseus-${key}`, url]),
      ...Object.entries(audioPaths.pianoRight).map(([key, url]) => [`piano-right-${key}`, url]),
      ...Object.entries(audioPaths.pianoLeft).map(([key, url]) => [`piano-left-${key}`, url]),
    ];
    const results = await Promise.allSettled(entries.map(async ([key, url]) => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Could not load ${key}`);
      this.buffers.set(key, await this.context.decodeAudioData(await response.arrayBuffer()));
    }));
    const failed = results.filter((result) => result.status === "rejected").length;
    page.modelStatus.textContent = failed ? `Tracking ready · ${failed} audio files unavailable` : "Tracking and audio ready";
  }

  play(key, volume = 1) {
    const buffer = this.buffers.get(key);
    if (!buffer || this.context?.state !== "running") return false;
    const source = this.context.createBufferSource();
    const gain = this.context.createGain();
    source.buffer = buffer;
    gain.gain.value = Math.max(0, Math.min(1, volume));
    source.connect(gain).connect(this.context.destination);
    source.start();
    return true;
  }
}

state.audio = new AudioBank();

async function initializeModels() {
  if (state.modelsPromise) return state.modelsPromise;
  state.modelsPromise = (async () => {
    page.modelStatus.textContent = "Loading hand and pose tracking…";
    const vision = await FilesetResolver.forVisionTasks(VISION_WASM);
    [state.handLandmarker, state.poseLandmarker] = await Promise.all([
      HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: HAND_MODEL },
        runningMode: "VIDEO",
        numHands: 2,
        minHandDetectionConfidence: 0.5,
        minHandPresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
      }),
      PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: POSE_MODEL },
        runningMode: "VIDEO",
        numPoses: 1,
        minPoseDetectionConfidence: 0.5,
        minPosePresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
        outputSegmentationMasks: false,
      }),
    ]);
  })().catch((error) => {
    state.modelsPromise = null;
    throw error;
  });
  return state.modelsPromise;
}

async function startSession() {
  if (!navigator.mediaDevices?.getUserMedia) {
    page.cameraStatus.textContent = "Camera preview is unavailable in this browser";
    return;
  }
  try {
    stopCamera();
    page.cameraStatus.textContent = "Requesting camera permission…";
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    page.camera.srcObject = state.stream;
    await page.camera.play();
    state.paused = false;
    page.pauseOverlay.classList.add("hidden");
    page.placeholder.classList.add("hidden");
    page.cameraStatus.textContent = "Loading gesture models…";
    await initializeModels();
    state.running = true;
    page.cameraStatus.textContent = "Camera on · show a gesture";
    state.animationFrame ??= requestAnimationFrame(processFrame);
  } catch (error) {
    stopCamera();
    page.cameraStatus.textContent = error.name === "NotAllowedError"
      ? "Camera permission was not granted"
      : "Could not start the camera or gesture models";
    page.modelStatus.textContent = "Unable to initialize browser tracking";
    page.placeholder.classList.remove("hidden");
    console.error("HandyBand could not start.", error);
  }
}

function stopCamera() {
  state.running = false;
  state.paused = false;
  if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = null;
  state.lastVideoTime = -1;
  state.stream?.getTracks().forEach((track) => track.stop());
  state.stream = null;
  page.camera.srcObject = null;
  clearOverlay();
}

function processFrame(timestamp) {
  state.animationFrame = null;
  if (!state.running || state.paused) return;
  if (page.camera.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && page.camera.currentTime !== state.lastVideoTime) {
    state.lastVideoTime = page.camera.currentTime;
    // The animation-frame clock includes time spent in synchronous inference. The
    // video timeline measures the interval between the camera frames themselves.
    const motionTimestamp = Math.round(page.camera.currentTime * 1000);
    const handResult = state.handLandmarker.detectForVideo(page.camera, timestamp);
    const hands = observationsFrom(handResult);
    const fingerStatuses = updateFingerRecognizer(hands, motionTimestamp);
    const poseResult = page.style.value === "Odysseus"
      ? state.poseLandmarker.detectForVideo(page.camera, timestamp)
      : null;
    const drumStatuses = page.style.value === "Odysseus"
      ? updateDrumRecognizer(hands, forearmsFrom(poseResult), motionTimestamp)
      : [];
    state.latestFingerStatuses = fingerStatuses;
    state.latestDrumStatuses = drumStatuses;
    playFingerEvents(fingerStatuses);
    playDrumEvents(drumStatuses.flatMap((status) => status.event ? [status.event] : []), motionTimestamp);
    drawLandmarks(hands);
    updateLiveText(fingerStatuses, drumStatuses);
  }
  state.animationFrame = requestAnimationFrame(processFrame);
}

function pauseTracking() {
  if (!state.running || state.paused) return;
  state.paused = true;
  if (state.animationFrame) cancelAnimationFrame(state.animationFrame);
  state.animationFrame = null;
  state.pendingDrum = null;
  page.pauseOverlay.classList.remove("hidden");
  page.cameraStatus.textContent = "Tracking paused";
  page.gestureState.textContent = "PAUSED — TAP THE SCREEN TO RESUME";
}

function resumeTracking() {
  if (!state.running || !state.paused) return;
  state.paused = false;
  page.pauseOverlay.classList.add("hidden");
  page.cameraStatus.textContent = "Camera on · show a gesture";
  page.gestureState.textContent = "TRACKING RESUMED";
  state.animationFrame ??= requestAnimationFrame(processFrame);
}

function toggleTracking() {
  if (state.paused) resumeTracking();
  else pauseTracking();
}

async function toggleFullscreen() {
  try {
    const active = document.fullscreenElement || document.webkitFullscreenElement;
    if (!active) {
      const request = document.documentElement.requestFullscreen
        || document.documentElement.webkitRequestFullscreen;
      if (!request) throw new Error("Fullscreen API is not supported");
      await request.call(document.documentElement);
    } else {
      const exit = document.exitFullscreen || document.webkitExitFullscreen;
      if (!exit) throw new Error("Fullscreen API is not supported");
      await exit.call(document);
    }
  } catch (error) {
    page.modelStatus.textContent = "FULLSCREEN IS NOT AVAILABLE IN THIS BROWSER";
    console.warn("Fullscreen mode is unavailable.", error);
  }
}

function updateFullscreenLabel() {
  page.fullscreenButton.textContent = document.fullscreenElement || document.webkitFullscreenElement
    ? "⌟ EXIT FULLSCREEN"
    : "⌜ FULLSCREEN";
}

function observationsFrom(result) {
  return (result.landmarks ?? []).map((landmarks, index) => ({
    handedness: result.handednesses?.[index]?.[0]?.categoryName ?? "Unknown",
    landmarks,
    fingers: classifyFingers(landmarks),
  }));
}

function forearmsFrom(result) {
  const landmarks = result?.landmarks?.[0];
  if (!landmarks) return [];
  return [["Left", 13, 15], ["Right", 14, 16]].flatMap(([handedness, elbowIndex, wristIndex]) => {
    const elbow = landmarks[elbowIndex];
    const wrist = landmarks[wristIndex];
    const confidence = Math.min(elbow?.visibility ?? 0, wrist?.visibility ?? 0);
    return confidence >= 0.5 ? [{ handedness, elbow, wrist, confidence }] : [];
  });
}

function classifyFingers(landmarks) {
  if (landmarks.length !== 21) return [];
  const wrist = landmarks[0];
  return FINGER_ORDER.map((name) => {
    const [baseIndex, firstIndex, secondIndex, tipIndex] = FINGER_JOINTS[name];
    const base = landmarks[baseIndex];
    const first = landmarks[firstIndex];
    const second = landmarks[secondIndex];
    const tip = landmarks[tipIndex];
    return {
      name,
      extended: jointAngle(base, first, second) >= 155
        && jointAngle(first, second, tip) >= 155
        && distance(wrist, tip) > distance(wrist, first),
    };
  });
}

function jointAngle(first, joint, last) {
  const a = [first.x - joint.x, first.y - joint.y, first.z - joint.z];
  const b = [last.x - joint.x, last.y - joint.y, last.z - joint.z];
  const magnitudeA = Math.hypot(...a);
  const magnitudeB = Math.hypot(...b);
  if (!magnitudeA || !magnitudeB) return 0;
  const cosine = a.reduce((sum, value, index) => sum + value * b[index], 0) / (magnitudeA * magnitudeB);
  return Math.acos(Math.max(-1, Math.min(1, cosine))) * 180 / Math.PI;
}

function distance(first, second) {
  return Math.hypot(first.x - second.x, first.y - second.y, first.z - second.z);
}

function numberedGesture(hand) {
  if (!hand) return null;
  const fingers = new Map(hand.fingers.map((finger) => [finger.name, finger.extended]));
  if (FINGER_ORDER.some((name) => !fingers.has(name))) return null;
  return GESTURE_PATTERNS.get(FINGER_ORDER.map((name) => fingers.get(name) ? "1" : "0").join("")) ?? null;
}

function newFingerState() {
  return { candidate: null, since: null, confirmed: null, lastTrigger: null, lastEvent: null };
}

function updateFingerRecognizer(hands, timestamp) {
  const handsBySide = new Map(hands.map((hand) => [hand.handedness, hand]));
  return ["Left", "Right"].map((handedness) => {
    const current = state.fingerStates.get(handedness);
    const gesture = numberedGesture(handsBySide.get(handedness));
    if (gesture === null) {
      current.candidate = current.since = current.confirmed = null;
      return { handedness, phase: handsBySide.has(handedness) ? "NO GESTURE" : "TRACKING LOST" };
    }
    if (gesture !== current.candidate) {
      current.candidate = gesture;
      current.since = timestamp;
      current.confirmed = null;
    }
    if (timestamp - current.since < HOLD_MS) {
      return { handedness, phase: "HOLDING", gesture };
    }
    current.confirmed = gesture;
    const canTrigger = current.lastTrigger === null
      || timestamp - current.lastTrigger >= safetyIntervalFor(handedness)
      || current.lastEvent?.gesture !== gesture;
    if (!canTrigger) return { handedness, phase: "SAFETY WAIT", gesture };
    const event = { handedness, gesture, timestamp };
    current.lastTrigger = timestamp;
    current.lastEvent = event;
    return { handedness, phase: "TRIGGERED", gesture, event };
  });
}

function safetyIntervalFor(handedness) {
  return STYLE_SAFETY_INTERVALS_MS[page.style.value][handedness];
}

function newDrumState() {
  return { previousWristY: null, previousElbowY: null, previousTimestamp: null, filteredSpeed: 0,
    swinging: false, strokeStarted: 0, strokeDistance: 0, lastTrigger: null };
}

function resetDrumTracking(current) {
  current.previousWristY = current.previousElbowY = current.previousTimestamp = null;
  current.filteredSpeed = 0;
  current.swinging = false;
  current.strokeDistance = 0;
}

function rememberForearm(current, forearm, timestamp) {
  current.previousWristY = forearm.wrist.y;
  current.previousElbowY = forearm.elbow.y;
  current.previousTimestamp = timestamp;
}

function updateDrumRecognizer(hands, forearms, timestamp) {
  const handsBySide = new Map(hands.map((hand) => [hand.handedness, hand]));
  const forearmsBySide = new Map(forearms.map((forearm) => [forearm.handedness, forearm]));
  return ["Left", "Right"].map((handedness) => updateDrumHand(
    handedness, handsBySide.get(handedness), forearmsBySide.get(handedness), timestamp,
  ));
}

function updateDrumHand(handedness, hand, forearm, timestamp) {
  const current = state.drumStates.get(handedness);
  const openHand = Boolean(hand && hand.fingers.every((finger) => finger.extended));
  if (!forearm) {
    resetDrumTracking(current);
    return { handedness, phase: "TRACKING LOST", openHand };
  }
  const armLength = Math.hypot(forearm.wrist.x - forearm.elbow.x, forearm.wrist.y - forearm.elbow.y);
  if (current.previousTimestamp === null || armLength <= 0.000001) {
    rememberForearm(current, forearm, timestamp);
    return { handedness, phase: drumIdlePhase(current, timestamp), openHand };
  }
  const elapsedSeconds = (timestamp - current.previousTimestamp) / 1000;
  if (elapsedSeconds <= 0 || elapsedSeconds > 0.2) {
    resetDrumTracking(current);
    rememberForearm(current, forearm, timestamp);
    return { handedness, phase: drumIdlePhase(current, timestamp), openHand };
  }
  const wristDelta = forearm.wrist.y - current.previousWristY;
  const elbowDelta = forearm.elbow.y - current.previousElbowY;
  const relativeDownwardDelta = wristDelta - elbowDelta;
  const relativeSpeed = relativeDownwardDelta / armLength / elapsedSeconds;
  const rawSpeed = wristDelta > 0 ? relativeSpeed : Math.min(0, relativeSpeed);
  current.filteredSpeed = DRUM.speedSmoothing * rawSpeed
    + (1 - DRUM.speedSmoothing) * current.filteredSpeed;
  rememberForearm(current, forearm, timestamp);
  const cooldown = current.lastTrigger !== null && timestamp - current.lastTrigger < DRUM.cooldownMs;
  if (!current.swinging && !cooldown && current.filteredSpeed >= DRUM.startSpeed) {
    current.swinging = true;
    current.strokeStarted = timestamp;
    current.strokeDistance = 0;
  }
  if (!current.swinging) return { handedness, phase: drumIdlePhase(current, timestamp), openHand };
  current.strokeDistance += Math.max(0, relativeDownwardDelta / armLength);
  if (current.filteredSpeed > DRUM.stopSpeed) return { handedness, phase: "SWINGING", openHand };
  const duration = Math.max((timestamp - current.strokeStarted) / 1000, 0.000001);
  const strokeDistance = current.strokeDistance;
  const averageSpeed = strokeDistance / duration;
  current.swinging = false;
  current.strokeDistance = 0;
  if (strokeDistance < DRUM.minimumDistance
    || averageSpeed < DRUM.minimumAverageSpeed
    || !Number.isFinite(averageSpeed)) {
    return { handedness, phase: drumIdlePhase(current, timestamp), openHand };
  }
  current.lastTrigger = timestamp;
  const progress = Math.max(0, Math.min(1,
    (averageSpeed - DRUM.minimumAverageSpeed) / (DRUM.maximumVolumeSpeed - DRUM.minimumAverageSpeed)));
  const volume = DRUM.minimumVolume + progress ** DRUM.volumeExponent
    * (DRUM.maximumVolume - DRUM.minimumVolume);
  return { handedness, phase: "DRUM HIT", openHand, event: { handedness, timestamp, volume } };
}

function drumIdlePhase(current, timestamp) {
  if (current.lastTrigger !== null && timestamp - current.lastTrigger < DRUM.cooldownMs) return "COOLDOWN";
  return "ARMED";
}

function playFingerEvents(statuses) {
  for (const status of statuses) {
    if (!status.event) continue;
    const key = page.style.value === "Piano"
      ? `piano-${status.handedness === "Left" ? "left" : "right"}-${status.gesture}`
      : `odysseus-${status.gesture}`;
    state.audio.play(key);
  }
}

function playDrumEvents(events, timestamp) {
  const remaining = [...events];
  if (state.pendingDrum) {
    const partnerIndex = remaining.findIndex((event) => event.handedness !== state.pendingDrum.handedness
      && event.timestamp - state.pendingDrum.timestamp <= 80);
    if (partnerIndex >= 0) {
      const partner = remaining.splice(partnerIndex, 1)[0];
      state.audio.play("drum", Math.min(1, state.pendingDrum.volume + partner.volume));
      state.pendingDrum = null;
    } else if (timestamp - state.pendingDrum.timestamp >= 80) {
      state.audio.play("drum", state.pendingDrum.volume);
      state.pendingDrum = null;
    }
  }
  for (const event of remaining) {
    if (!state.pendingDrum) state.pendingDrum = event;
    else if (event.handedness !== state.pendingDrum.handedness) {
      state.audio.play("drum", Math.min(1, event.volume + state.pendingDrum.volume));
      state.pendingDrum = null;
    } else {
      state.audio.play("drum", state.pendingDrum.volume);
      state.pendingDrum = event;
    }
  }
}

function updateLiveText(fingerStatuses, drumStatuses) {
  const fingers = fingerStatuses.filter((status) => status.phase !== "TRACKING LOST")
    .map((status) => `${status.handedness} ${status.gesture ?? "—"}: ${status.phase}`);
  const drums = drumStatuses.filter((status) => status.phase === "DRUM HIT" || status.phase === "SWINGING")
    .map((status) => `${status.handedness}: ${status.phase}`);
  page.gestureState.textContent = [...fingers, ...drums].join(" · ") || "Show one or both hands to the camera";
}

function drawLandmarks(hands) {
  const canvas = page.overlay;
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.round(rect.width * ratio);
  const height = Math.round(rect.height * ratio);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, width, height);
  if (!page.camera.videoWidth || !page.camera.videoHeight) return;
  const sourceRatio = page.camera.videoWidth / page.camera.videoHeight;
  const viewRatio = rect.width / rect.height;
  const drawWidth = (sourceRatio > viewRatio ? rect.width : rect.height * sourceRatio) * ratio;
  const drawHeight = (sourceRatio > viewRatio ? rect.width / sourceRatio : rect.height) * ratio;
  const offsetX = (width - drawWidth) / 2;
  const offsetY = (height - drawHeight) / 2;
  context.lineWidth = Math.max(1.5, 2 * ratio);
  for (const hand of hands) {
    context.strokeStyle = hand.handedness === "Left" ? "#8fddc0" : "#f3ca7c";
    context.fillStyle = "#ffffff";
    context.beginPath();
    for (const [from, to] of HAND_CONNECTIONS) {
      const start = hand.landmarks[from];
      const end = hand.landmarks[to];
      context.moveTo(offsetX + start.x * drawWidth, offsetY + start.y * drawHeight);
      context.lineTo(offsetX + end.x * drawWidth, offsetY + end.y * drawHeight);
    }
    context.stroke();
    for (const landmark of hand.landmarks) {
      context.beginPath();
      context.arc(offsetX + landmark.x * drawWidth, offsetY + landmark.y * drawHeight, 2.3 * ratio, 0, Math.PI * 2);
      context.fill();
    }
  }
}

function clearOverlay() {
  const context = page.overlay.getContext("2d");
  context.clearRect(0, 0, page.overlay.width, page.overlay.height);
}

function resetRecognizers() {
  state.fingerStates = new Map(["Left", "Right"].map((side) => [side, newFingerState()]));
  state.drumStates = new Map(["Left", "Right"].map((side) => [side, newDrumState()]));
  state.pendingDrum = null;
}

page.cameraScreen.addEventListener("click", (event) => {
  if (!event.target.closest("button")) toggleTracking();
});
page.cameraScreen.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    toggleTracking();
  }
});
page.pauseOverlay.addEventListener("click", (event) => {
  event.stopPropagation();
  resumeTracking();
});
page.fullscreenButton.addEventListener("click", toggleFullscreen);
document.addEventListener("fullscreenchange", updateFullscreenLabel);
document.addEventListener("webkitfullscreenchange", updateFullscreenLabel);
async function toggleSound() {
  if (state.audio.context?.state === "running") {
    await state.audio.suspend();
    page.cameraButton.textContent = "SOUND OFF";
    page.modelStatus.textContent = "TRACKING ACTIVE · SOUND OFF";
    return;
  }
  try {
    await state.audio.unlock();
    page.cameraButton.textContent = "SOUND ON";
    page.modelStatus.textContent = "TRACKING AND AUDIO READY";
  } catch (error) {
    page.cameraButton.textContent = "SOUND UNAVAILABLE";
    page.modelStatus.textContent = "AUDIO COULD NOT BE ENABLED";
    console.error("HandyBand audio could not start.", error);
  }
}
page.style.addEventListener("change", () => {
  resetRecognizers();
  page.styleNote.textContent = page.style.value === "Piano"
    ? "PIANO: LEFT HAND 1.64S / RIGHT HAND 0.82S REARM."
    : "ODYSSEUS: 75S REARM PER HAND, PLUS ARM-DOWNSTROKE DRUMS.";
  page.gestureState.textContent = page.style.value === "Piano"
    ? "Show a numbered hand shape and hold it briefly"
    : "Make a downward drum stroke";
  updateChannelControls();
});

function selectChannel(style) {
  if (page.style.value === style) return;
  page.style.value = style;
  page.style.dispatchEvent(new Event("change"));
}

function updateChannelControls() {
  page.channelReadout.textContent = page.style.value.toUpperCase();
  page.channelButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.channel === page.style.value));
  });
}

page.cameraButton.addEventListener("click", toggleSound);
page.channelButtons.forEach((button) => {
  button.addEventListener("click", () => selectChannel(button.dataset.channel));
});
updateChannelControls();
window.addEventListener("pagehide", () => {
  stopCamera();
  state.handLandmarker?.close();
  state.poseLandmarker?.close();
});

void startSession();
