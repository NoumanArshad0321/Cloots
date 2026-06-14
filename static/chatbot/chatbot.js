(function () {
  const toggle = document.getElementById("cloots-chatbot-toggle");
  const win = document.getElementById("cloots-chatbot-window");
  const closeBtn = document.getElementById("cloots-chatbot-close");
  const form = document.getElementById("cloots-chatbot-form");
  const input = document.getElementById("cloots-chatbot-input");
  const messages = document.getElementById("cloots-chatbot-messages");
  const URL = window.CLOOTS_CHATBOT_URL || "/chatbot/api/ask/";

  function show() { win.hidden = false; input.focus(); }
  function hide() { win.hidden = true; }

  toggle.addEventListener("click", () => (win.hidden ? show() : hide()));
  closeBtn.addEventListener("click", hide);

  function addMessage(text, who) {
    const div = document.createElement("div");
    div.className = "cc-msg " + who;
    // very small markdown: **bold** and newlines
    div.innerHTML = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    addMessage(text, "user");
    input.value = "";
    try {
      const res = await fetch(URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      addMessage(data.reply || "Sorry, something went wrong.", "bot");
    } catch (err) {
      addMessage("Network error. Please try again.", "bot");
    }
  });
})();
