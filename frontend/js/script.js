// Settings 
const API = "";                       // same server as the website

let currentStatus = "all";            // sidebar filter
let currentCategory = "all";          // category pill filter
let currency = "$";
let editingSku = null;                // null = adding a new product
let sessionId = "s" + Date.now();     // one id per chat (gives the agent its memory)
let waiting = false;                  // true while the agent is thinking
let searchTimer = null;

const CATEGORY_ICONS = {
  "Fruits & Vegetables": "",
  "Dairy & Eggs": "",
  "Bakery": "",
  "Meat & Seafood": "",
  "Beverages": "",
  "Snacks": "",
  "Pantry": "",
  "Household & Personal Care": "",
};

const SUGGESTIONS = [
  "Tell me about Fresh Milk",
  "Which products are out of stock?",
  "Analyse milk, bread and eggs for the last 14 days",
  "Give me the monthly sales summary of Cola",
  "What were the most sold items this week?",
  "Make a weekly sales report PDF",
];


// Helpers
// Short way to get an element
function $(id) {
  return document.getElementById(id);
}

// Stop product names from being read as HTML
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function money(number) {
  return currency + Number(number).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Talk to the Python backend
async function api(path, method = "GET", body = null) {
  const options = { method: method, headers: { "Content-Type": "application/json" } };
  if (body) {
    options.body = JSON.stringify(body);
  }
  const response = await fetch(API + path, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Something went wrong.");
  }
  return data;
}

function showToast(text) {
  const toast = $("toast");
  toast.textContent = text;
  toast.classList.add("show");
  setTimeout(function () { toast.classList.remove("show"); }, 2600);
}

function openModal(id) { $(id).classList.add("open"); }
function closeModal(id) { $(id).classList.remove("open"); }

function statusClass(status) {
  if (status === "In Stock") return "in";
  if (status === "Low Stock") return "low";
  return "out";
}

function iconFor(category) {
  return CATEGORY_ICONS[category] || "";
}


//Dashboard nuber
async function loadSummary() {
  const s = await api("/api/summary");
  currency = s.currency;
  $("statTotal").textContent = s.total;
  $("statIn").textContent = s.in_stock;
  $("statLow").textContent = s.low_stock;
  $("statOut").textContent = s.out_of_stock;
  $("statRevenue").textContent = money(s.week_revenue);
  $("alertBadge").textContent = s.low_stock + s.out_of_stock;
  $("modelNote").textContent = "AI model: " + s.model;
}

async function loadCategories() {
  const categories = await api("/api/categories");

  let html = '<button class="pill active" data-category="all">All</button>';
  let options = "";
  for (const c of categories) {
    html += '<button class="pill" data-category="' + escapeHtml(c) + '">' + escapeHtml(c) + "</button>";
    options += '<option value="' + escapeHtml(c) + '">';
  }
  $("categoryPills").innerHTML = html;
  $("categoryList").innerHTML = options;
}


// Product list
async function loadProducts() {
  const search = $("searchInput").value.trim();
  const url = "/api/products?search=" + encodeURIComponent(search)
    + "&category=" + encodeURIComponent(currentCategory)
    + "&status=" + encodeURIComponent(currentStatus);

  const products = await api(url);

  let html = "";
  for (const p of products) {
    html += '<button class="product card" data-sku="' + p.sku + '">'
      + '<div class="product-icon">' + iconFor(p.category) + "</div>"
      + '<div class="product-name">' + escapeHtml(p.name) + "</div>"
      + '<div class="product-brand">' + escapeHtml(p.brand) + " · " + escapeHtml(p.unit) + "</div>"
      + '<div class="product-row"><span class="product-price">' + money(p.price) + "</span>"
      + '<span class="product-stock">' + p.stock + " in stock</span></div>"
      + '<span class="status ' + statusClass(p.status) + '">' + p.status + "</span>"
      + "</button>";
  }
  if (products.length === 0) {
    html = '<div class="empty">No products found.</div>';
  }

  $("productGrid").innerHTML = html;
  $("productCount").textContent = products.length + " product(s)";
  $("listTitle").textContent = currentStatus === "all" ? "All Products" : currentStatus;
}

async function refreshAll() {
  try {
    await loadSummary();
    await loadProducts();
  } catch (e) {
    showToast("Could not load data: " + e.message);
  }
}


// Product popup
async function openProduct(sku) {
  try {
    const p = await api("/api/products/" + sku);
    const margin = ((p.price - p.cost_price) / p.price * 100).toFixed(0);

    $("detailContent").innerHTML =
      '<div class="detail-head"><div class="product-icon">' + iconFor(p.category) + "</div>"
      + "<div><h2>" + escapeHtml(p.name) + "</h2>"
      + '<span class="status ' + statusClass(p.status) + '">' + p.status + "</span></div></div>"
      + '<p class="detail-desc">' + escapeHtml(p.description || "No description.") + "</p>"
      + '<div class="detail-grid">'
      + "<div><span>Product code</span>" + p.sku + "</div>"
      + "<div><span>Brand</span>" + escapeHtml(p.brand) + "</div>"
      + "<div><span>Category</span>" + escapeHtml(p.category) + "</div>"
      + "<div><span>Unit</span>" + escapeHtml(p.unit) + "</div>"
      + "<div><span>Selling price</span>" + money(p.price) + "</div>"
      + "<div><span>Cost price</span>" + money(p.cost_price) + " (margin " + margin + "%)</div>"
      + "<div><span>Stock</span>" + p.stock + " units</div>"
      + "<div><span>Reorder level</span>" + p.reorder_level + " units</div>"
      + "<div><span>Supplier</span>" + escapeHtml(p.supplier) + "</div>"
      + "<div><span>Origin</span>" + escapeHtml(p.origin) + "</div>"
      + "<div><span>Storage</span>" + escapeHtml(p.storage) + "</div>"
      + "<div><span>Shelf life</span>" + p.shelf_life_days + " days</div>"
      + "<div><span>Barcode</span>" + escapeHtml(p.barcode) + "</div>"
      + "<div><span>Last restocked</span>" + p.last_restocked + "</div>"
      + "</div>"
      + '<div class="action-row"><input type="number" id="qtyRestock" min="1" placeholder="Qty">'
      + '<button class="btn" data-action="restock" data-sku="' + p.sku + '">Restock</button>'
      + '<input type="number" id="qtySell" min="1" placeholder="Qty">'
      + '<button class="btn ghost" data-action="sell" data-sku="' + p.sku + '">Record Sale</button></div>'
      + '<div class="action-row">'
      + '<button class="btn ghost" data-action="edit" data-sku="' + p.sku + '">Edit</button>'
      + '<button class="btn danger" data-action="delete" data-sku="' + p.sku + '">Delete</button></div>';

    openModal("detailModal");
  } catch (e) {
    showToast(e.message);
  }
}

async function handleProductAction(action, sku) {
  try {
    if (action === "restock") {
      const qty = Number($("qtyRestock").value);
      await api("/api/products/" + sku + "/restock", "POST", { quantity: qty });
      showToast("Stock updated.");
      await refreshAll();
      await openProduct(sku);
    } else if (action === "sell") {
      const qty = Number($("qtySell").value);
      await api("/api/products/" + sku + "/sell", "POST", { quantity: qty });
      showToast("Sale recorded.");
      await refreshAll();
      await openProduct(sku);
    } else if (action === "edit") {
      closeModal("detailModal");
      await openForm(sku);
    } else if (action === "delete") {
      if (confirm("Delete this product? This cannot be undone.")) {
        await api("/api/products/" + sku, "DELETE");
        closeModal("detailModal");
        showToast("Product deleted.");
        await loadCategories();
        await refreshAll();
      }
    }
  } catch (e) {
    showToast(e.message);
  }
}


// add and edit Form
const FORM_FIELDS = ["name", "brand", "category", "unit", "price", "cost_price", "stock",
  "reorder_level", "shelf_life_days", "supplier", "origin", "storage", "barcode", "description"];

async function openForm(sku) {
  editingSku = sku;
  $("formError").textContent = "";

  if (sku) {
    const p = await api("/api/products/" + sku);
    for (const field of FORM_FIELDS) {
      $("f_" + field).value = p[field];
    }
    $("formTitle").textContent = "Edit Product";
  } else {
    for (const field of FORM_FIELDS) {
      $("f_" + field).value = "";
    }
    $("formTitle").textContent = "Add Product";
  }
  openModal("formModal");
}

async function saveProduct() {
  const data = {};
  for (const field of FORM_FIELDS) {
    data[field] = $("f_" + field).value;
  }

  try {
    if (editingSku) {
      await api("/api/products/" + editingSku, "PUT", data);
      showToast("Product updated.");
    } else {
      await api("/api/products", "POST", data);
      showToast("Product added.");
    }
    closeModal("formModal");
    await loadCategories();
    await refreshAll();
  } catch (e) {
    $("formError").textContent = e.message;
  }
}


// ---------- 7. AI CHAT ----------
function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good Morning";
  if (hour < 18) return "Good Afternoon";
  return "Good Evening";
}

function showGreeting() {
  $("chatMessages").innerHTML =
    '<div class="greeting" id="greeting"><span class="orb big"></span>'
    + "<h3>" + getGreeting() + " <b>Store Manager</b>, what's on your mind?</h3>"
    + '<div class="suggestions" id="suggestions"></div></div>';

  let html = "";
  for (const text of SUGGESTIONS) {
    html += '<button class="suggestion">' + escapeHtml(text) + "</button>";
  }
  $("suggestions").innerHTML = html;
}

// Turn the model's text into simple HTML (bold, bullet lines, paragraphs)
function formatChatText(text) {
  const lines = escapeHtml(text).split("\n");
  let html = "";
  let inList = false;

  for (let line of lines) {
    line = line.trim().replace(/^#+\s*/, "").replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    const isBullet = line.startsWith("- ") || line.startsWith("* ");

    if (isBullet) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += "<li>" + line.slice(2) + "</li>";
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (line !== "") { html += "<p>" + line + "</p>"; }
    }
  }
  if (inList) html += "</ul>";
  return html;
}

function scrollChat() {
  const box = $("chatMessages");
  box.scrollTop = box.scrollHeight;
}

function addUserMessage(text) {
  const greeting = $("greeting");
  if (greeting) greeting.remove();

  const div = document.createElement("div");
  div.className = "msg user";
  div.innerHTML = '<div class="msg-name">You</div><div class="msg-body">' + escapeHtml(text) + "</div>";
  $("chatMessages").appendChild(div);
  scrollChat();
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg bot";
  div.id = "typing";
  div.innerHTML = '<div class="msg-name"><span class="orb"></span>Stock Sense</div>'
    + '<div class="msg-body"><div class="typing"><span></span><span></span><span></span></div>'
    + "<small>Thinking and checking the database...</small></div>";
  $("chatMessages").appendChild(div);
  scrollChat();
}

// The list of tools the agent used (the trace)
function buildTraceHtml(steps) {
  if (!steps || steps.length === 0) return "";

  let rows = "";
  for (const step of steps) {
    if (step.type === "call") {
      rows += "<div>🔧 Called <code>" + escapeHtml(step.name) + "</code> with <code>"
        + escapeHtml(JSON.stringify(step.args)) + "</code></div>";
    } else {
      rows += "<div>📥 Returned: <code>" + escapeHtml(step.output.slice(0, 160)) + "...</code></div>";
    }
  }
  return '<details class="trace"><summary>Tool trace (' + steps.length + " steps)</summary>"
    + '<div class="trace-box">' + rows + "</div></details>";
}

function addBotMessage(result) {
  const typing = $("typing");
  if (typing) typing.remove();

  let html = '<div class="msg-name"><span class="orb"></span>Stock Sense</div>'
    + '<div class="msg-body">' + formatChatText(result.answer) + "</div>";

  if (result.pdf_file) {
    html += '<a class="download-btn" href="/reports/' + encodeURIComponent(result.pdf_file)
      + '" download>📄 Download PDF Report</a>';
  }
  html += buildTraceHtml(result.steps);
  html += '<div class="msg-tools"><button class="thumb">👍</button><button class="thumb">👎</button></div>';

  const div = document.createElement("div");
  div.className = "msg bot" + (result.error ? " error" : "");
  div.innerHTML = html;
  $("chatMessages").appendChild(div);
  scrollChat();
}

async function sendMessage(text) {
  text = text.trim();
  if (text === "" || waiting) return;

  waiting = true;
  $("sendBtn").disabled = true;
  $("chatInput").value = "";

  addUserMessage(text);
  addTyping();

  try {
    const result = await api("/api/chat", "POST", { message: text, session_id: sessionId });
    addBotMessage(result);
  } catch (e) {
    addBotMessage({ answer: "Error: " + e.message, steps: [], pdf_file: null, error: true });
  }

  waiting = false;
  $("sendBtn").disabled = false;
  $("chatInput").focus();
}

function newChat() {
  sessionId = "s" + Date.now();        // a new id = the agent forgets the old chat
  showGreeting();
}


// ---------- 8. START ----------
function setupEvents() {
  // sidebar status filter
  document.querySelectorAll(".nav-item[data-status]").forEach(function (button) {
    button.addEventListener("click", function () {
      document.querySelectorAll(".nav-item[data-status]").forEach(function (b) { b.classList.remove("active"); });
      button.classList.add("active");
      currentStatus = button.dataset.status;
      loadProducts();
    });
  });

  $("addProductBtn").addEventListener("click", function () { openForm(null); });
  $("refreshBtn").addEventListener("click", function () { refreshAll(); showToast("Data refreshed."); });
  $("newChatBtn").addEventListener("click", newChat);
  $("saveProductBtn").addEventListener("click", saveProduct);

  // bell: show products that need attention
  $("bellBtn").addEventListener("click", function () {
    document.querySelector('.nav-item[data-status="Low Stock"]').click();
  });

  // search box (waits a moment after typing stops)
  $("searchInput").addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadProducts, 300);
  });

  // category pills
  $("categoryPills").addEventListener("click", function (event) {
    const pill = event.target.closest(".pill");
    if (!pill) return;
    document.querySelectorAll(".pill").forEach(function (p) { p.classList.remove("active"); });
    pill.classList.add("active");
    currentCategory = pill.dataset.category;
    loadProducts();
  });

  // product cards
  $("productGrid").addEventListener("click", function (event) {
    const card = event.target.closest(".product");
    if (card) openProduct(card.dataset.sku);
  });

  // popup buttons
  $("detailContent").addEventListener("click", function (event) {
    const button = event.target.closest("[data-action]");
    if (button) handleProductAction(button.dataset.action, button.dataset.sku);
  });
  document.querySelectorAll("[data-close]").forEach(function (button) {
    button.addEventListener("click", function () { closeModal(button.dataset.close); });
  });
  document.querySelectorAll(".modal-bg").forEach(function (bg) {
    bg.addEventListener("click", function (event) {
      if (event.target === bg) bg.classList.remove("open");
    });
  });

  // chat
  $("sendBtn").addEventListener("click", function () { sendMessage($("chatInput").value); });
  $("chatInput").addEventListener("keydown", function (event) {
    if (event.key === "Enter") sendMessage($("chatInput").value);
  });
  $("chatMessages").addEventListener("click", function (event) {
    const suggestion = event.target.closest(".suggestion");
    if (suggestion) sendMessage(suggestion.textContent);

    const thumb = event.target.closest(".thumb");
    if (thumb) thumb.classList.toggle("on");
  });
}

async function start() {
  setupEvents();
  showGreeting();
  try {
    await loadCategories();
    await refreshAll();
  } catch (e) {
    showToast("Cannot reach the backend. Is app.py running?");
  }
}

start();
