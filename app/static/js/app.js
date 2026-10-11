function filterRestaurants() {
  const input = document.getElementById("searchInput");
  if (!input) return;
  const q = (input.value || "").toLowerCase().trim();
  document.querySelectorAll("[data-restaurant-card]").forEach((el) => {
    const name = (el.getAttribute("data-name") || "").toLowerCase();
    const desc = (el.getAttribute("data-desc") || "").toLowerCase();
    const ok = !q || name.includes(q) || desc.includes(q);
    el.style.display = ok ? "" : "none";
  });
}

document.addEventListener("input", (e) => {
  if (e.target && e.target.id === "searchInput") filterRestaurants();
});
