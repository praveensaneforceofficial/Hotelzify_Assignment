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

  // Support clickable product chips: **[Product Name]**
  let formattedText = text
    .replace(/\*\*\[(.*?)\]\*\*/g, (match, p1) => {
      return `<button type="button" onclick="selectProduct('${p1}')" class="inline-flex items-center gap-1 px-2.5 py-1 my-0.5 rounded-lg bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold border border-blue-300 transition text-xs cursor-pointer shadow-xs"><i class="fa-solid fa-tag text-[10px] text-blue-600"></i> ${p1}</button>`;
    })
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
  
  logs.slice().reverse().forEach((log, index) => {
    const card = document.createElement("div");
    card.className = "rounded-lg bg-white border border-slate-200 shadow-xs text-[11px] overflow-hidden";
    
    const isPost = log.method === "POST";
    const badgeColor = isPost 
      ? "text-amber-800 bg-amber-100 border-amber-300" 
      : "text-blue-800 bg-blue-100 border-blue-300";
    
    card.innerHTML = `
      <details class="group" ${index === 0 ? "open" : ""}>
        <summary class="flex items-center justify-between p-2.5 cursor-pointer hover:bg-slate-50 transition list-none">
          <div class="flex items-center gap-2">
            <span class="font-bold font-mono ${badgeColor} px-2 py-0.5 rounded border text-[10px]">
              ${log.method} ${log.api_name}
            </span>
            <span class="text-emerald-600 font-semibold text-[10px]">● 200 OK</span>
          </div>
          <div class="flex items-center gap-2 text-slate-500 text-[10px]">
            <span>${Math.round(log.duration_ms)}ms</span>
            <span class="text-blue-600 font-medium group-open:rotate-180 transition-transform">
              <i class="fa-solid fa-chevron-down"></i>
            </span>
          </div>
        </summary>
        
        <div class="p-3 border-t border-slate-100 bg-slate-50/70 space-y-2">
          <div>
            <span class="text-slate-500 font-semibold block text-[10px] uppercase tracking-wider">Payload</span>
            <pre class="bg-white p-2 rounded border border-slate-200 text-slate-800 text-[10px] overflow-x-auto font-mono mt-0.5">${JSON.stringify(log.payload, null, 2)}</pre>
          </div>
          <div>
            <span class="text-slate-500 font-semibold block text-[10px] uppercase tracking-wider">Response</span>
            <pre class="bg-white p-2 rounded border border-slate-200 text-emerald-800 text-[10px] overflow-x-auto font-mono mt-0.5">${JSON.stringify(log.response, null, 2)}</pre>
          </div>
        </div>
      </details>
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


function selectProduct(productName) {
  const prompt = `I need ${productName}`;
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
  currentSessionId = "session_" + Math.random().toString(36).substring(2, 8);
  document.getElementById("session-id-display").innerText = currentSessionId;
  chatMessages.innerHTML = `
    <div class="flex items-start gap-2.5">
      <div class="w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs shrink-0 font-bold">
        AI
      </div>
      <div class="chat-bubble-bot p-3 rounded-xl max-w-[85%] text-sm shadow-sm leading-relaxed">
        Session reset! Click any product below to get started, or ask about our catalog:
        <div class="mt-2.5 flex flex-wrap gap-1.5">
          <button type="button" onclick="selectProduct('AeroMesh Wi-Fi 6E Home Pack')" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold border border-blue-300 transition text-xs cursor-pointer shadow-xs">
            <i class="fa-solid fa-wifi text-[10px] text-blue-600"></i> AeroMesh Wi-Fi 6E
          </button>
          <button type="button" onclick="selectProduct('SyncHub Conference Bar')" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold border border-blue-300 transition text-xs cursor-pointer shadow-xs">
            <i class="fa-solid fa-video text-[10px] text-blue-600"></i> SyncHub Conference Bar
          </button>
          <button type="button" onclick="selectProduct('AirPods Pro 2nd Gen')" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold border border-blue-300 transition text-xs cursor-pointer shadow-xs">
            <i class="fa-solid fa-headphones text-[10px] text-blue-600"></i> AirPods Pro 2nd Gen
          </button>
          <button type="button" onclick="sendMessage('What are the products available?')" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium border border-slate-300 transition text-xs cursor-pointer">
            <i class="fa-solid fa-list text-[10px] text-slate-500"></i> View All Products
          </button>
        </div>
      </div>
    </div>
  `;
  apiLogsContainer.innerHTML = `<div class="text-slate-400 italic p-4 text-center">Session reset. Logs cleared.</div>`;
});
