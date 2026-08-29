import "./styles.css";
import { invoke } from "@tauri-apps/api/core";

const $ = <T extends Element>(selector: string) => document.querySelector<T>(selector)!;
const connection = $<HTMLSpanElement>("#connection");
const sidebarState = $<HTMLElement>("#sidebar-state");
const presenceCopy = $<HTMLParagraphElement>("#presence-copy");
const homeGreeting = $<HTMLParagraphElement>("#home-greeting");
const messages = $<HTMLElement>("#messages");
const form = $<HTMLFormElement>("#chat-form");
const input = $<HTMLInputElement>("#chat-input");
const sendButton = $<HTMLButtonElement>("#send-button");
const micButton = $<HTMLButtonElement>("#mic-button");
const soundToggle = $<HTMLButtonElement>("#sound-toggle");
const computerToggle = $<HTMLButtonElement>("#computer-toggle");
const computerStop = $<HTMLButtonElement>("#computer-stop");
const computerRefresh = $<HTMLButtonElement>("#computer-refresh");
const computerStatus = $<HTMLParagraphElement>("#computer-status");
const computerHelp = $<HTMLParagraphElement>("#computer-help");
const computerContext = $<HTMLElement>("#computer-context");
const computerText = $<HTMLInputElement>("#computer-text");
const computerType = $<HTMLButtonElement>("#computer-type");
const statusJson = $<HTMLElement>("#status-json");
const activityFeed = $<HTMLOListElement>("#activity-feed");
const homeModel = $<HTMLElement>("#home-model");
const homeBrainDetail = $<HTMLElement>("#home-brain-detail");
const homeComputer = $<HTMLElement>("#home-computer");
const homeComputerDetail = $<HTMLElement>("#home-computer-detail");
const homeConversationCount = $<HTMLElement>("#home-conversation-count");
const deviceCore = $<HTMLElement>("#device-core");
const deviceModel = $<HTMLElement>("#device-model");
const pageTitle = $<HTMLHeadingElement>("#page-title");
const pageKicker = $<HTMLParagraphElement>("#page-kicker");
const navButtons = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-view]"));
const views = Array.from(document.querySelectorAll<HTMLElement>(".view"));
const soundSettingKey = "orbit-sound-enabled";

type ComputerStatus = { active: boolean; remainingSeconds?: number; targetWindow?: string | null };
type CoreStatus = { runtimeState: string; localBrain: { model: string; running: boolean } | null; computerMode?: ComputerStatus };
type ComputerControl = { id: string; name: string; type: "Button" | "CheckBox" | "Document" | "Edit" | "Hyperlink" | "ListItem" | "MenuItem" | "TabItem" };
type ComputerContext = { windowTitle: string; controls: ComputerControl[] };
type SpeechResultItem = { transcript: string };
type SpeechRecognitionEvent = Event & { results: ArrayLike<ArrayLike<SpeechResultItem>> };
type SpeechRecognitionErrorEvent = Event & { error: string };
type SpeechRecognitionInstance = { lang: string; interimResults: boolean; maxAlternatives: number; onresult: ((event: SpeechRecognitionEvent) => void) | null; onerror: ((event: SpeechRecognitionErrorEvent) => void) | null; onend: (() => void) | null; start: () => void; stop: () => void };
type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;
type SpeechRecognitionWindow = Window & { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };

const pageMeta: Record<string, { title: string; kicker: string }> = {
  home: { title: "God morgon.", kicker: "ORBIT / ÖVERSIKT" }, conversation: { title: "Samtal.", kicker: "ORBIT / NÄRVARO" }, memory: { title: "Minne.", kicker: "ORBIT / KONTINUITET" }, activity: { title: "Aktivitet.", kicker: "ORBIT / INSYN" }, devices: { title: "Enheter.", kicker: "ORBIT / LOKALT" }, automations: { title: "Automationer.", kicker: "ORBIT / DATORLÄGE" }, status: { title: "Status.", kicker: "ORBIT / RUNTIMESANNING" }, settings: { title: "Inställningar.", kicker: "ORBIT / DITT VAL" },
};

let thinking = false;
let listening = false;
let coreReady = false;
let computerModeActive = false;
let latestComputerStatus: ComputerStatus = { active: false };
let selectedTextControl: string | undefined;
let messageCount = 0;
let soundEnabled = window.localStorage.getItem(soundSettingKey) !== "false";
let audioContext: AudioContext | undefined;
let recognition: SpeechRecognitionInstance | undefined;
let speakingTimer: number | undefined;

async function orbitInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!("__TAURI_INTERNALS__" in window)) {
    throw new Error("Öppna ORBIT via Desktop-appen för att ansluta till lokal Core.");
  }
  return invoke<T>(command, args);
}

function logActivity(label: string) {
  activityFeed.querySelector(".activity-empty")?.remove();
  const item = document.createElement("li");
  const time = new Intl.DateTimeFormat("sv-SE", { hour: "2-digit", minute: "2-digit" }).format(new Date());
  item.innerHTML = `<time>${time}</time><span>${label}</span>`;
  activityFeed.prepend(item);
}

function showView(name: string) {
  if (!pageMeta[name]) return;
  document.body.dataset.view = name;
  for (const view of views) { const active = view.id === `view-${name}`; view.hidden = !active; view.classList.toggle("is-active", active); }
  for (const nav of navButtons) nav.classList.toggle("is-active", nav.dataset.view === name);
  pageTitle.textContent = pageMeta[name].title;
  pageKicker.textContent = pageMeta[name].kicker;
  if (name === "conversation") window.setTimeout(() => input.focus(), 180);
}

function setConnection(label: string, state: "waiting" | "ready" | "failed") {
  const changed = connection.textContent !== label || !connection.classList.contains(`connection--${state}`);
  connection.textContent = label;
  connection.className = `connection connection--${state}`;
  sidebarState.textContent = state === "ready" ? "Ansluten" : state === "failed" ? "Behöver åtgärd" : "Startar";
  document.body.dataset.connection = state;
  if (changed && state !== "waiting") logActivity(label);
}

function addMessage(role: "orbit" | "user", content: string) {
  const message = document.createElement("article");
  message.className = `message message--${role}`;
  message.textContent = content;
  messages.append(message);
  messages.scrollTop = messages.scrollHeight;
  homeConversationCount.textContent = String(++messageCount);
}

function setThinking(active: boolean) { thinking = active; document.body.classList.toggle("is-thinking", active); if (active) presenceCopy.textContent = "ORBIT samlar tankarna…"; }
function setListening(active: boolean) { listening = active; document.body.classList.toggle("is-listening", active); micButton.textContent = active ? "Lyssnar…" : "Prata"; micButton.setAttribute("aria-pressed", String(active)); if (active) presenceCopy.textContent = "Jag lyssnar."; }
function showSpeakingExpression() {
  if (speakingTimer) window.clearTimeout(speakingTimer);
  document.body.classList.add("is-speaking");
  speakingTimer = window.setTimeout(() => document.body.classList.remove("is-speaking"), 1500);
}
function updateSoundToggle() { soundToggle.textContent = `Ljud: ${soundEnabled ? "På" : "Av"}`; soundToggle.setAttribute("aria-pressed", String(soundEnabled)); }

function updateComputerMode(_status: ComputerStatus) {
  latestComputerStatus = { active: false };
  computerModeActive = false;
  computerStatus.textContent = "Blockerat";
  homeComputer.textContent = "Blockerat";
  homeComputerDetail.textContent = "Väntar på verifierad Capability Truth";
  computerToggle.textContent = "Ej tillgängligt";
  computerToggle.disabled = true;
  computerStop.disabled = true;
  computerRefresh.disabled = true;
  computerText.disabled = true;
  computerType.disabled = true;
  computerHelp.textContent = "Datorläge är blockerat tills nya Core har en verifierad och fail-safe styrningskapacitet.";
}

function clearComputerContext(message: string) { selectedTextControl = undefined; computerContext.textContent = message; computerText.value = ""; }

function renderComputerContext(context: ComputerContext) {
  selectedTextControl = undefined;
  computerContext.replaceChildren();
  const title = document.createElement("p"); title.className = "computer-context__title"; title.textContent = context.windowTitle; computerContext.append(title);
  if (!context.controls.length) { const empty = document.createElement("p"); empty.textContent = "Jag hittade inga användbara kontroller i den här appen ännu."; computerContext.append(empty); updateComputerMode({ active: computerModeActive }); return; }
  for (const control of context.controls) {
    const item = document.createElement("button"); item.type = "button"; item.className = "computer-control";
    if (control.type === "Edit" || control.type === "Document") {
      item.textContent = `Välj textfält: ${control.name}`;
      item.addEventListener("click", () => { selectedTextControl = control.id; computerHelp.textContent = `Valt fält: ${control.name}. Skriv text nedan och tryck Skriv.`; updateComputerMode({ active: true }); });
    } else { item.textContent = `Klicka: ${control.name}`; item.addEventListener("click", () => void clickComputerControl(control)); }
    computerContext.append(item);
  }
  updateComputerMode({ active: computerModeActive });
}

async function computerRequest<T>(path: string, payload?: object): Promise<T> {
  const command = {
    "/v1/computer/status": "core_computer_status",
    "/v1/computer/context": "core_computer_context",
    "/v1/computer/session": "core_computer_session",
    "/v1/computer/click": "core_computer_click",
    "/v1/computer/type": "core_computer_type",
  }[path];
  if (!command) throw new Error("Datorläget har en okänd åtgärd.");
  return orbitInvoke<T>(command, payload as Record<string, unknown> | undefined);
}

async function startComputerMode() { try { const status = await computerRequest<ComputerStatus>("/v1/computer/session", { action: "start" }); clearComputerContext("Växla nu till appen du vill använda. Kom sedan tillbaka och tryck Hämta aktiv app."); updateComputerMode(status); addMessage("orbit", "Datorläget är på i tio minuter. Jag arbetar bara i den app du väljer."); logActivity("Datorläge startades för 10 minuter."); playReplySound(); } catch (error) { addMessage("orbit", error instanceof Error ? error.message : "Datorläget kunde inte starta."); } }
async function stopComputerMode() { try { const status = await computerRequest<ComputerStatus>("/v1/computer/session", { action: "stop" }); clearComputerContext("Datorläget är stoppat."); updateComputerMode(status); addMessage("orbit", "Datorläget är stoppat."); logActivity("Datorläge stoppades av dig."); } catch (error) { addMessage("orbit", error instanceof Error ? error.message : "Datorläget kunde inte stoppas."); } }
async function refreshComputerContext() { try { const context = await computerRequest<ComputerContext>("/v1/computer/context"); renderComputerContext(context); logActivity(`Hämtade synliga kontroller från ${context.windowTitle}.`); } catch (error) { clearComputerContext(error instanceof Error ? error.message : "Kunde inte hämta aktiv app."); } }
async function clickComputerControl(control: ComputerControl) { try { await computerRequest("/v1/computer/click", { id: control.id }); addMessage("orbit", `Klickade på ${control.name}.`); logActivity(`Klickade på ${control.name}.`); playReplySound(); } catch (error) { addMessage("orbit", error instanceof Error ? error.message : "Klicket kunde inte genomföras."); } }

function normaliseComputerText(value: string) { return value.toLocaleLowerCase("sv-SE").replace(/\s+/g, " ").trim(); }
async function tryComputerClickCommand(text: string): Promise<boolean> {
  if (!computerModeActive || !/\b(klicka|tryck|valj|välj)\b/i.test(text)) return false;
  try {
    const context = await computerRequest<ComputerContext>("/v1/computer/context");
    const requested = normaliseComputerText(text);
    const control = context.controls.filter((item) => item.type !== "Edit" && item.type !== "Document").sort((left, right) => right.name.length - left.name.length).find((item) => requested.includes(normaliseComputerText(item.name)));
    if (!control) return false;
    await computerRequest("/v1/computer/click", { id: control.id }); addMessage("orbit", `Klickade på ${control.name}.`); logActivity(`Klickade på ${control.name} på din begäran.`); playReplySound(); return true;
  } catch (error) { addMessage("orbit", error instanceof Error ? error.message : "Klicket kunde inte genomföras."); return true; }
}
async function typeIntoComputerControl() { const text = computerText.value.trim(); if (!selectedTextControl || !text) return; try { await computerRequest("/v1/computer/type", { id: selectedTextControl, text }); computerText.value = ""; addMessage("orbit", "Texten är skriven i valt fält."); logActivity("Skrev text i det valda fältet."); playReplySound(); } catch (error) { addMessage("orbit", error instanceof Error ? error.message : "Texten kunde inte skrivas."); } }

function playTone(frequency: number, delay: number, duration: number, volume = 0.022) { if (!soundEnabled || !window.AudioContext) return; audioContext ??= new window.AudioContext(); const now = audioContext.currentTime + delay; const oscillator = audioContext.createOscillator(); const gain = audioContext.createGain(); oscillator.type = "triangle"; oscillator.frequency.setValueAtTime(frequency, now); gain.gain.setValueAtTime(.0001, now); gain.gain.exponentialRampToValueAtTime(volume, now + .025); gain.gain.exponentialRampToValueAtTime(.0001, now + duration); oscillator.connect(gain).connect(audioContext.destination); oscillator.start(now); oscillator.stop(now + duration + .02); }
function playThinkingSound() { playTone(174, 0, .18, .018); playTone(196, .15, .22, .016); }
function playReplySound() { playTone(392, 0, .1); playTone(523, .09, .18, .02); }

async function startListening() {
  const speechWindow = window as SpeechRecognitionWindow;
  const SpeechRecognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
  if (!SpeechRecognition) { addMessage("orbit", "Röstigenkänning stöds inte i den här Windows-versionen ännu."); return; }
  try { const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); stream.getTracks().forEach((track) => track.stop()); } catch { addMessage("orbit", "Tillåt mikrofonen i Windows för att ORBIT ska kunna höra dig."); return; }
  recognition = new SpeechRecognition(); recognition.lang = "sv-SE"; recognition.interimResults = true; recognition.maxAlternatives = 1;
  recognition.onresult = (event) => { input.value = Array.from(event.results).map((result) => result[0]?.transcript ?? "").join("").trim(); };
  recognition.onerror = (event) => { if (event.error !== "aborted") addMessage("orbit", "Jag hörde inte riktigt. Tryck Prata och försök igen."); };
  recognition.onend = () => { setListening(false); void refreshStatus(); };
  setListening(true); try { recognition.start(); } catch { setListening(false); addMessage("orbit", "Mikrofonen kunde inte starta. Försök igen."); }
}

function renderRuntime(status: CoreStatus) {
  statusJson.textContent = JSON.stringify(status, null, 2);
  const brain = status.localBrain;
  homeModel.textContent = brain?.running ? brain.model : "Inte redo";
  homeBrainDetail.textContent = brain?.running ? "Svarar lokalt via Ollama" : "Ollama behöver startas";
  deviceCore.textContent = `Core är ${status.runtimeState === "ready" ? "redo" : status.runtimeState}.`;
  deviceModel.textContent = brain?.running ? `${brain.model} körs lokalt.` : "Ingen körande lokal modell hittades.";
}

async function refreshStatus() {
  try {
    const status = await orbitInvoke<CoreStatus>("core_status"); renderRuntime(status);
    if (status.localBrain?.running) { setConnection(`Lokal hjärna: ${status.localBrain.model}`, "ready"); if (!thinking) presenceCopy.textContent = "Jag är här. Vad vill du göra?"; homeGreeting.textContent = "ORBIT är vaken och din lokala hjärna är ansluten."; coreReady = true; input.disabled = false; sendButton.disabled = false; micButton.disabled = false; updateComputerMode(status.computerMode ?? { active: false }); return; }
    setConnection("Core körs, Ollama saknas", "failed"); coreReady = false; updateComputerMode({ active: false }); if (!thinking) presenceCopy.textContent = "Core är vaken, men jag hittar ingen lokal modell ännu.";
  } catch { setConnection("Väntar på Core", "waiting"); coreReady = false; renderRuntime({ runtimeState: "offline", localBrain: null }); updateComputerMode({ active: false }); if (!thinking) presenceCopy.textContent = "Jag vaknar och letar efter min lokala hjärna."; homeGreeting.textContent = "Starta ORBIT så ansluter vi här automatiskt."; }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault(); const text = input.value.trim(); if (!text) return;
  addMessage("user", text); input.value = ""; input.disabled = true; sendButton.disabled = true; micButton.disabled = true;
  if (await tryComputerClickCommand(text)) { input.disabled = false; sendButton.disabled = false; micButton.disabled = false; input.focus(); return; }
  setThinking(true); playThinkingSound();
  try { const payload = await orbitInvoke<{ content?: string }>("core_conversation", { text }); addMessage("orbit", payload.content ?? "Jag fick inget svar."); showSpeakingExpression(); playReplySound(); } catch (error) { addMessage("orbit", error instanceof Error ? error.message : "Orbit kunde inte svara."); }
  finally { setThinking(false); input.disabled = false; sendButton.disabled = false; micButton.disabled = false; input.focus(); }
});

micButton.addEventListener("click", () => { if (listening) recognition?.stop(); else void startListening(); });
soundToggle.addEventListener("click", () => { soundEnabled = !soundEnabled; window.localStorage.setItem(soundSettingKey, String(soundEnabled)); updateSoundToggle(); if (soundEnabled) playReplySound(); });
computerToggle.addEventListener("click", () => void startComputerMode()); computerStop.addEventListener("click", () => void stopComputerMode()); computerRefresh.addEventListener("click", () => void refreshComputerContext()); computerType.addEventListener("click", () => void typeIntoComputerControl());
for (const nav of navButtons) nav.addEventListener("click", () => showView(nav.dataset.view ?? "home"));
for (const open of document.querySelectorAll<HTMLButtonElement>("[data-open-view]")) open.addEventListener("click", () => showView(open.dataset.openView ?? "home"));
for (const prompt of document.querySelectorAll<HTMLButtonElement>("[data-prompt]")) prompt.addEventListener("click", () => { input.value = prompt.dataset.prompt ?? ""; input.focus(); });
input.disabled = true; sendButton.disabled = true; micButton.disabled = true; computerToggle.disabled = true; computerStop.disabled = true; computerRefresh.disabled = true; computerText.disabled = true; computerType.disabled = true;
updateSoundToggle(); updateComputerMode({ active: false }); showView("home"); void refreshStatus();
window.setInterval(() => { if (!document.hidden) void refreshStatus(); }, 3000);
window.addEventListener("online", () => { setConnection("Återansluter till Core", "waiting"); void refreshStatus(); });
