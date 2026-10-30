// Client logic for AI Sales Agent
let currentSessionId = "session_" + Math.random().toString(36).substring(2, 8);
document.getElementById("session-id-display").innerText = currentSessionId;

const chatMessages = document.getElementById("chat-messages");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const btnSend = document.getElementById("btn-send");
const btnReset = document.getElementById("btn-reset");
const apiLogsContainer = document.getElementById("api-logs-container");


function appendMessage(sender, text, isError = false) {
  const isUser = sender === "user";
  const wrapper = document.createElement("div");
  wrapper.className = `flex items-start gap-2.5 ${isUser ? "justify-end" : ""}`;

  const iconDiv = document.createElement("div");
  iconDiv.className = `w-8 h-8 rounded-full flex items-center justify-center text-xs shrink-0 font-bold ${
    isUser ? "bg-slate-700 text-white order-2" : "bg-blue-100 text-blue-600"
  }`;
  iconDiv.innerText = isUser ? "You" : "AI";

  const bubble = document.createElement("div");
  bubble.className = `${
    isUser ? "chat-bubble-user" : "chat-bubble-bot"
  } p-3 rounded-xl max-w-[85%] text-sm shadow-sm leading-relaxed`;
  
  if (isError) {
    bubble.classList.add("bg-red-50", "border-red-200", "text-red-700");
  }

  let formattedText = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
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


function renderApiLogs(logs) {
  if (!logs || logs.length === 0) return;
  apiLogsContainer.innerHTML = "";
  
  logs.slice().reverse().forEach(log => {
    const card = document.createElement("div");
    card.className = "p-3 rounded-lg bg-white border border-slate-200 shadow-xs text-[11px] space-y-1.5";
    
    const isPost = log.method === "POST";
    const badgeColor = isPost ? "text-amber-700 bg-amber-50 border-amber-200" : "text-blue-700 bg-blue-50 border-blue-200";
    
    card.innerHTML = `
      <div class="flex items-center justify-between border-b border-slate-100 pb-1">
        <span class="font-bold ${badgeColor} px-2 py-0.5 rounded border text-[10px]">${log.method} ${log.api_name}</span>
        <span class="text-slate-400 text-[10px]">${Math.round(log.duration_ms)}ms</span>
      </div>
      <div>
        <span class="text-slate-500 font-semibold block text-[10px]">Payload:</span>
        <pre class="bg-slate-50 p-1.5 rounded border border-slate-100 text-slate-700 text-[10px] overflow-x-auto">${JSON.stringify(log.payload, null, 2)}</pre>
      </div>
      <div>
        <span class="text-slate-500 font-semibold block text-[10px]">Response:</span>
        <pre class="bg-slate-50 p-1.5 rounded border border-slate-100 text-emerald-700 text-[10px] overflow-x-auto">${JSON.stringify(log.response, null, 2)}</pre>
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
    renderApiLogs(data.api_call_logs);

  } catch (err) {
    appendMessage("bot", `Network error: ${err.message}`, true);
  } finally {
    btnSend.disabled = false;
    chatInput.focus();
  }
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
  currentSessionId = "session_" + Math.random().toString(36).substring(2, 8);
  document.getElementById("session-id-display").innerText = currentSessionId;
  chatMessages.innerHTML = `
    <div class="flex items-start gap-2.5">
      <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs shrink-0 font-bold">
        AI
      </div>
      <div class="chat-bubble-bot p-3 rounded-xl max-w-[85%] text-sm shadow-sm leading-relaxed">
        Session reset! Welcome back. How many rooms or tables are you looking to equip today?
      </div>
    </div>
  `;
  apiLogsContainer.innerHTML = `<div class="text-slate-400 italic p-4 text-center">Session reset. Logs cleared.</div>`;
});
