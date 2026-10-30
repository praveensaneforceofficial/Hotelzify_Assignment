// Client logic for Hotelzify AI Sales Agent
let currentSessionId = "session_" + Math.random().toString(36).substring(2, 9);
document.getElementById("session-id-display").innerText = currentSessionId;

const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const btnReset = document.getElementById("btn-reset");

// State elements
const stateSku = document.getElementById("state-sku");
const statePlan = document.getElementById("state-plan");
const stateQty = document.getElementById("state-qty");
const statePromo = document.getElementById("state-promo");
const statePrice = document.getElementById("state-price");
const stateConfirmed = document.getElementById("state-confirmed");
const bookingBadge = document.getElementById("booking-badge");
const apiLogsContainer = document.getElementById("api-logs-container");


function appendMessage(sender, text, isError = false) {
  const isUser = sender === "user";
  const wrapper = document.createElement("div");
  wrapper.className = `flex items-start gap-2.5 ${isUser ? "justify-end" : ""}`;

  const iconDiv = document.createElement("div");
  iconDiv.className = `w-8 h-8 rounded-lg flex items-center justify-center text-xs shrink-0 mt-0.5 ${
    isUser ? "bg-slate-700 text-white order-2" : "bg-blue-600 text-white"
  }`;
  iconDiv.innerHTML = isUser ? `<i class="fa-solid fa-user"></i>` : `<i class="fa-solid fa-robot"></i>`;

  const bubble = document.createElement("div");
  bubble.className = `${
    isUser ? "chat-bubble-user" : "chat-bubble-bot"
  } p-3.5 rounded-2xl ${isUser ? "rounded-tr-sm" : "rounded-tl-sm"} max-w-[85%] text-sm shadow-sm leading-relaxed`;
  
  if (isError) {
    bubble.classList.add("bg-red-500/10", "border-red-500/30", "text-red-300");
  }

  // Support basic markdown bold
  let formattedText = text
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-blue-900">$1</strong>')
    .replace(/\n/g, '<br/>');

  bubble.innerHTML = formattedText;

  wrapper.appendChild(iconDiv);
  if (isUser) {
    wrapper.insertBefore(bubble, iconDiv);
  } else {
    wrapper.appendChild(bubble);
  }

  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}


function updateStateInspector(state) {
  if (!state) return;
  stateSku.innerText = state.sku_id ? `${state.sku_id} (${state.product_name || ''})` : "None";
  statePlan.innerText = state.plan_code || "None";
  stateQty.innerText = `${state.required_capacity || 0} rooms → ${state.quantity || 0} unit(s)`;
  
  const promoLabel = state.promo_code ? `${state.promo_code} (${Math.round(state.discount_rate * 100)}%)` : "None (0%)";
  statePromo.innerText = `Tier ${state.discount_tier} (${promoLabel})`;
  
  statePrice.innerText = `$${(state.final_price || 0).toFixed(2)}`;
  stateConfirmed.innerText = state.is_confirmed ? "✅ Yes" : "❌ No";
  stateConfirmed.className = state.is_confirmed ? "font-mono font-semibold text-emerald-400" : "font-mono font-semibold text-amber-400";

  bookingBadge.innerText = state.booking_status;
  if (state.booking_status === "BOOKED") {
    bookingBadge.className = "text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase tracking-wide";
  } else if (state.booking_status === "IN_PROGRESS") {
    bookingBadge.className = "text-[11px] font-mono px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-300 border border-yellow-500/30 uppercase tracking-wide";
  } else {
    bookingBadge.className = "text-[11px] font-mono px-2 py-0.5 rounded bg-slate-700 text-slate-300 uppercase tracking-wide";
  }
}


function renderApiLogs(logs) {
  if (!logs || logs.length === 0) return;
  apiLogsContainer.innerHTML = "";
  
  // Display latest logs top-first or bottom-first
  logs.slice().reverse().forEach(log => {
    const card = document.createElement("div");
    card.className = "p-2.5 rounded-lg bg-slate-900 border border-slate-700/80 text-[11px] space-y-1";
    
    const methodColor = log.method === "POST" ? "text-amber-400 bg-amber-400/10 border-amber-400/20" : "text-blue-400 bg-blue-400/10 border-blue-400/20";
    
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-bold ${methodColor} px-1.5 py-0.5 rounded border text-[10px]">${log.method} ${log.api_name}</span>
        <span class="text-slate-500 text-[10px]">${Math.round(log.duration_ms)}ms</span>
      </div>
      <div class="text-slate-400">
        <span class="text-slate-500">Payload:</span> ${JSON.stringify(log.payload)}
      </div>
      <div class="text-emerald-400">
        <span class="text-slate-500">Response:</span> ${JSON.stringify(log.response)}
      </div>
    `;
    apiLogsContainer.appendChild(card);
  });
}


async function sendMessage(text) {
  if (!text || !text.trim()) return;
  appendMessage("user", text);
  chatInput.value = "";
  btnSend.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        message: text
      })
    });

    const data = await res.json();
    if (!res.ok) {
      appendMessage("bot", `Error: ${data.detail || "Server error"}`, true);
      return;
    }

    appendMessage("bot", data.reply);
    updateStateInspector(data.state);
    renderApiLogs(data.api_call_logs);

  } catch (err) {
    appendMessage("bot", `Network error: ${err.message}`, true);
  } finally {
    btnSend.disabled = false;
    chatInput.focus();
  }
}


// Scenario 4 Demo: Rapid Double Confirmation
async function sendDoubleConfirmation() {
  const confirmText = "Yes, book it!";
  appendMessage("user", confirmText + " (Triggering 2 simultaneous requests...)");

  btnSend.disabled = true;

  // Dispatch 2 concurrent POST requests with the same session ID
  const p1 = fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: currentSessionId, message: confirmText })
  }).then(r => r.json());

  const p2 = fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: currentSessionId, message: confirmText })
  }).then(r => r.json());

  const [res1, res2] = await Promise.all([p1, p2]);

  appendMessage("bot", res1.reply);
  if (res2.reply !== res1.reply) {
    appendMessage("bot", `[Simultaneous Response]: ${res2.reply}`);
  }
  updateStateInspector(res2.state || res1.state);
  renderApiLogs(res2.api_call_logs || res1.api_call_logs);
  btnSend.disabled = false;
}


function sendQuickPrompt(prompt) {
  chatInput.value = prompt;
  sendMessage(prompt);
}


chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(chatInput.value);
});


btnReset.addEventListener("click", async () => {
  await fetch("/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: currentSessionId })
  });
  currentSessionId = "session_" + Math.random().toString(36).substring(2, 9);
  document.getElementById("session-id-display").innerText = currentSessionId;
  chatMessages.innerHTML = `
    <div class="flex items-start gap-2.5">
      <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white text-xs shrink-0 mt-0.5">
        <i class="fa-solid fa-robot"></i>
      </div>
      <div class="chat-bubble-bot p-3.5 rounded-2xl rounded-tl-sm max-w-[85%] text-sm shadow-sm">
        <p class="font-semibold text-blue-700 mb-1">Hotelzify Sales Concierge</p>
        Session reset! Welcome back. How many rooms or guests are you looking to equip today?
      </div>
    </div>
  `;
  updateStateInspector({
    sku_id: null,
    plan_code: null,
    required_capacity: 0,
    quantity: 0,
    discount_tier: 0,
    promo_code: null,
    discount_rate: 0,
    final_price: 0,
    is_confirmed: false,
    booking_status: "IDLE"
  });
  apiLogsContainer.innerHTML = `<div class="text-slate-500 italic p-3 text-center">Session reset. Logs cleared.</div>`;
});
