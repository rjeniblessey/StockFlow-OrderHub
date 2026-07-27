const API_BASE = "/api";

// ---------- tiny state ----------
const state = {
  role: "customer",       // which tab is selected on the auth screen
  mode: "login",          // "login" | "signup"
  accessToken: localStorage.getItem("access_token") || null,
  refreshToken: localStorage.getItem("refresh_token") || null,
  user: JSON.parse(localStorage.getItem("user") || "null"),
  products: [],
  orderTarget: null,
};

// ---------- element refs ----------
const el = {
  authScreen: document.getElementById("auth-screen"),
  appShell: document.getElementById("app-shell"),
  tagTabs: document.querySelectorAll(".tag-tab"),
  modeBtns: document.querySelectorAll(".mode-btn"),
  loginForm: document.getElementById("login-form"),
  signupForm: document.getElementById("signup-form"),
  authNote: document.getElementById("auth-note"),
  roleWords: document.querySelectorAll(".role-word"),

  whoBadge: document.getElementById("who-badge"),
  logoutBtn: document.getElementById("logout-btn"),
  adminView: document.getElementById("admin-view"),
  customerView: document.getElementById("customer-view"),

  productForm: document.getElementById("product-form"),
  productNote: document.getElementById("product-note"),
  adminProductList: document.getElementById("admin-product-list"),
  adminProductCount: document.getElementById("admin-product-count"),
  adminOrderList: document.getElementById("admin-order-list"),
  adminDeliveredList: document.getElementById("admin-delivered-list"),

  customerProductList: document.getElementById("customer-product-list"),
  customerProductCount: document.getElementById("customer-product-count"),
  customerOrderList: document.getElementById("customer-order-list"),
  customerDeliveredList: document.getElementById("customer-delivered-list"),

  modal: document.getElementById("order-modal"),
  orderModalTitle: document.getElementById("order-modal-title"),
  orderModalSub: document.getElementById("order-modal-sub"),
  orderQty: document.getElementById("order-qty"),
  orderModalTotal: document.getElementById("order-modal-total"),
  orderConfirm: document.getElementById("order-confirm"),
  orderCancel: document.getElementById("order-cancel"),
  orderModalNote: document.getElementById("order-modal-note"),

  toast: document.getElementById("toast"),
};

// ---------- helpers ----------
function toast(message, kind = "") {
  el.toast.textContent = message;
  el.toast.className = "toast" + (kind ? " " + kind : "");
  el.toast.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.toast.classList.add("hidden"), 3200);
}

function money(n) {
  return "₹" + Number(n).toFixed(2);
}

function saveSession(tokenResponse) {
  state.accessToken = tokenResponse.access_token;
  state.refreshToken = tokenResponse.refresh_token;
  state.user = tokenResponse.user;
  localStorage.setItem("access_token", state.accessToken);
  localStorage.setItem("refresh_token", state.refreshToken);
  localStorage.setItem("user", JSON.stringify(state.user));
}

function clearSession() {
  state.accessToken = null;
  state.refreshToken = null;
  state.user = null;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}

async function api(path, { method = "GET", body, auth = true, retry = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && state.accessToken) headers["Authorization"] = "Bearer " + state.accessToken;

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && auth && retry && state.refreshToken) {
    // try a silent refresh once, then retry the original call
    const refreshed = await tryRefresh();
    if (refreshed) return api(path, { method, body, auth, retry: false });
  }

  if (res.status === 204) return null;

  let data = null;
  try { data = await res.json(); } catch (_) { /* no body */ }

  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText || "Request failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

async function tryRefresh() {
  try {
    const res = await fetch(API_BASE + "/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
    if (!res.ok) throw new Error("refresh failed");
    const data = await res.json();
    saveSession(data);
    return true;
  } catch (_) {
    clearSession();
    showAuthScreen();
    return false;
  }
}

// ---------- auth screen behaviour ----------
el.tagTabs.forEach((btn) => {
  btn.addEventListener("click", () => {
    el.tagTabs.forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    btn.setAttribute("aria-selected", "true");
    el.tagTabs.forEach((b) => { if (b !== btn) b.setAttribute("aria-selected", "false"); });
    state.role = btn.dataset.role;
    el.roleWords.forEach((w) => (w.textContent = state.role === "admin" ? "seller" : "buyer"));
    el.authNote.textContent = "";
  });
});

el.modeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    el.modeBtns.forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    state.mode = btn.dataset.mode;
    el.loginForm.classList.toggle("hidden", state.mode !== "login");
    el.signupForm.classList.toggle("hidden", state.mode !== "signup");
    el.authNote.textContent = "";
  });
});

el.loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(el.loginForm);
  const payload = { username: fd.get("username").trim(), password: fd.get("password") };
  try {
    const data = await api(`/login/${state.role}`, { method: "POST", body: payload, auth: false });
    saveSession(data);
    el.authNote.textContent = "";
    enterApp();
  } catch (err) {
    el.authNote.classList.remove("success");
    el.authNote.textContent = err.message;
  }
});

el.signupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(el.signupForm);
  const payload = {
    username: fd.get("username").trim(),
    email: fd.get("email").trim(),
    password: fd.get("password"),
  };
  try {
    await api(`/signup/${state.role}`, { method: "POST", body: payload, auth: false });
    el.authNote.classList.add("success");
    el.authNote.textContent = "Account opened — you can log in now.";
    // switch to the login tab for convenience
    document.querySelector('.mode-btn[data-mode="login"]').click();
  } catch (err) {
    el.authNote.classList.remove("success");
    el.authNote.textContent = err.message;
  }
});

el.logoutBtn.addEventListener("click", async () => {
  try {
    if (state.refreshToken) {
      await api("/logout", { method: "POST", body: { refresh_token: state.refreshToken }, auth: false });
    }
  } catch (_) { /* ignore */ }
  clearSession();
  showAuthScreen();
});

// ---------- screen switching ----------
function showAuthScreen() {
  el.authScreen.classList.remove("hidden");
  el.appShell.classList.add("hidden");
  el.loginForm.reset();
  el.signupForm.reset();
}

function enterApp() {
  el.authScreen.classList.add("hidden");
  el.appShell.classList.remove("hidden");
  el.whoBadge.textContent = `${state.user.username} · ${state.user.role}`;

  const isAdmin = state.user.role === "admin";
  el.adminView.classList.toggle("hidden", !isAdmin);
  el.customerView.classList.toggle("hidden", isAdmin);

  loadProducts();
  loadOrders();
}

// ---------- products ----------
async function loadProducts() {
  try {
    const endpoint = state.user.role === "admin" ? "/product/mine" : "/product";
    state.products = await api(endpoint, { auth: state.user.role === "admin" });
    renderAdminProducts();
    renderCustomerProducts();
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderAdminProducts() {
  el.adminProductCount.textContent = `${state.products.length} item(s) on the shelf`;
  el.adminProductList.innerHTML = "";
  if (state.products.length === 0) {
    el.adminProductList.innerHTML = `<p class="empty-note">Nothing stocked yet — add your first product above.</p>`;
    return;
  }
  state.products.forEach((p) => {
    const row = document.createElement("div");
    row.className = "ledger-row";
    row.innerHTML = `
      <div class="lr-main">
        <span class="lr-name">${escapeHtml(p.name)}</span>
        <span class="lr-sub">${p.quantity} in stock${p.description ? " · " + escapeHtml(p.description) : ""}</span>
      </div>
      <div class="lr-main admin-row-actions" style="align-items:flex-end;">
        <span class="lr-amount">${money(p.price)}</span>
        <button data-id="${p.id}">Remove</button>
      </div>
    `;
    row.querySelector("button").addEventListener("click", () => deleteProduct(p.id));
    el.adminProductList.appendChild(row);
  });
}

async function deleteProduct(id) {
  if (!confirm("Remove this product from the shelf?")) return;
  try {
    await api(`/product/${id}`, { method: "DELETE" });
    toast("Product removed", "success");
    loadProducts();
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderCustomerProducts() {
  el.customerProductCount.textContent = `${state.products.length} item(s) available`;
  el.customerProductList.innerHTML = "";
  if (state.products.length === 0) {
    el.customerProductList.innerHTML = `<p class="empty-note">The shelf is empty right now — check back soon.</p>`;
    return;
  }
  state.products.forEach((p) => {
    const card = document.createElement("div");
    card.className = "shelf-card";
    const outOfStock = p.quantity <= 0;
    card.innerHTML = `
      <span class="sc-seller">Sold by ${escapeHtml(p.seller_username)}</span>
      <span class="sc-name">${escapeHtml(p.name)}</span>
      <span class="sc-desc">${p.description ? escapeHtml(p.description) : ""}</span>
      <div class="sc-meta">
        <span class="sc-price">${money(p.price)}</span>
        <span class="sc-stock ${p.quantity <= 3 ? "low" : ""}">${outOfStock ? "Out of stock" : p.quantity + " left"}</span>
      </div>
      <button ${outOfStock ? "disabled" : ""}>${outOfStock ? "Sold out" : "Order this"}</button>
    `;
    card.querySelector("button").addEventListener("click", () => openOrderModal(p));
    el.customerProductList.appendChild(card);
  });
}

el.productForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(el.productForm);
  const payload = {
    name: fd.get("name").trim(),
    description: fd.get("description").trim() || null,
    price: parseFloat(fd.get("price")),
    quantity: parseInt(fd.get("quantity"), 10),
  };
  try {
    await api("/product", { method: "POST", body: payload });
    el.productNote.classList.add("success");
    el.productNote.textContent = `“${payload.name}” is on the shelf.`;
    el.productForm.reset();
    loadProducts();
  } catch (err) {
    el.productNote.classList.remove("success");
    el.productNote.textContent = err.message;
  }
});

// ---------- orders ----------
function openOrderModal(product) {
  state.orderTarget = product;
  el.orderModalTitle.textContent = `Order ${product.name}`;
  el.orderModalSub.textContent = `${money(product.price)} each · ${product.quantity} available`;
  el.orderQty.value = 1;
  el.orderQty.max = product.quantity;
  el.orderModalNote.textContent = "";
  updateOrderTotal();
  el.modal.classList.remove("hidden");
}

function updateOrderTotal() {
  const qty = Math.max(1, parseInt(el.orderQty.value || "1", 10));
  const total = state.orderTarget ? state.orderTarget.price * qty : 0;
  el.orderModalTotal.textContent = "Total: " + money(total);
}
el.orderQty.addEventListener("input", updateOrderTotal);

el.orderCancel.addEventListener("click", () => el.modal.classList.add("hidden"));

el.orderConfirm.addEventListener("click", async () => {
  if (!state.orderTarget) return;
  const qty = Math.max(1, parseInt(el.orderQty.value || "1", 10));
  try {
    await api("/order", {
      method: "POST",
      body: { product_id: state.orderTarget.id, quantity: qty },
    });
    el.modal.classList.add("hidden");
    toast("Order placed", "success");
    loadProducts();
    loadOrders();
  } catch (err) {
    el.orderModalNote.textContent = err.message;
  }
});

async function loadOrders() {
  try {
    const orders = await api("/order");
    const active = orders.filter((o) => o.status !== "delivered");
    const delivered = orders.filter((o) => o.status === "delivered");

    if (state.user.role === "admin") {
      renderOrderList(el.adminOrderList, active, { showBuyer: true, role: "admin" });
      renderOrderList(el.adminDeliveredList, delivered, { showBuyer: true, role: "admin" });
    } else {
      renderOrderList(el.customerOrderList, active, { showBuyer: false, role: "customer" });
      renderOrderList(el.customerDeliveredList, delivered, { showBuyer: false, role: "customer" });
    }
  } catch (err) {
    toast(err.message, "error");
  }
}

const STATUS_LABEL = { placed: "Placed", shipped: "Sent", delivered: "Delivered" };

function renderOrderList(container, orders, { showBuyer, role }) {
  container.innerHTML = "";
  if (orders.length === 0) {
    container.innerHTML = `<p class="empty-note">Nothing here yet.</p>`;
    return;
  }
  orders.forEach((o) => {
    const row = document.createElement("div");
    row.className = "ledger-row";
    const when = new Date(o.created_at).toLocaleString();

    let actionHtml = "";
    if (role === "admin" && o.status === "placed") {
      actionHtml = `<button class="action-btn ship-btn" data-id="${o.id}">Send order</button>`;
    } else if (role === "customer" && o.status === "placed") {
      actionHtml = `<button class="action-btn cancel-btn" data-id="${o.id}">Remove</button>`;
    } else if (role === "customer" && o.status === "shipped") {
      actionHtml = `<button class="action-btn receive-btn" data-id="${o.id}">Mark received</button>`;
    }

    row.innerHTML = `
      <div class="lr-main">
        <span class="lr-name">${escapeHtml(o.product_name)} × ${o.quantity}</span>
        <span class="lr-sub">${showBuyer ? escapeHtml(o.customer_username) + " · " : ""}${when}</span>
      </div>
      <div class="lr-main" style="align-items:flex-end; gap:8px;">
        <span class="lr-amount">${money(o.total_price)}</span>
        <span class="status-pill status-${o.status}">${STATUS_LABEL[o.status]}</span>
        ${actionHtml}
      </div>
    `;

    const shipBtn = row.querySelector(".ship-btn");
    if (shipBtn) shipBtn.addEventListener("click", () => shipOrder(o.id));
    const cancelBtn = row.querySelector(".cancel-btn");
    if (cancelBtn) cancelBtn.addEventListener("click", () => cancelOrder(o.id));
    const receiveBtn = row.querySelector(".receive-btn");
    if (receiveBtn) receiveBtn.addEventListener("click", () => receiveOrder(o.id));

    container.appendChild(row);
  });
}

async function shipOrder(id) {
  try {
    await api(`/order/${id}/ship`, { method: "PATCH" });
    toast("Order marked as sent", "success");
    loadOrders();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function receiveOrder(id) {
  try {
    await api(`/order/${id}/deliver`, { method: "PATCH" });
    toast("Order marked as delivered", "success");
    loadOrders();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function cancelOrder(id) {
  if (!confirm("Remove this order? The stock will be returned to the shelf.")) return;
  try {
    await api(`/order/${id}`, { method: "DELETE" });
    toast("Order removed", "success");
    loadProducts();
    loadOrders();
  } catch (err) {
    toast(err.message, "error");
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------- boot ----------
(function boot() {
  if (state.accessToken && state.user) {
    enterApp();
  } else {
    showAuthScreen();
  }
})();
