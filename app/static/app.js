// Small bits of behaviour. No libraries, works offline.

// ---- Participate page: build the document checklist for the chosen company ----
(function () {
  const list = document.getElementById("doclist");
  if (!list || !window.DOCS) return;
  const company = document.getElementById("company");
  const pb = document.getElementById("pbbox");

  function render() {
    list.innerHTML = "";
    (window.DOCS[company.value] || []).forEach(function (d) {
      const row = document.createElement("label");
      row.className = "check";
      row.innerHTML = '<input type="checkbox" name="docs" value="' + d.key + '"' + (d.default ? " checked" : "") + '>' +
        '<span class="title"></span>' + (d.note ? '<span class="muted small"></span>' : "");
      row.querySelector(".title").textContent = d.title;
      if (d.note) row.querySelector(".muted").textContent = d.note;
      list.appendChild(row);
      if (d.kind === "upload") {
        const box = row.querySelector("input");
        const sync = function () { pb.hidden = !box.checked; };
        box.addEventListener("change", sync); sync();
      }
    });
  }
  company.addEventListener("change", render);
  render();
})();

// ---- Details page: live "final wording" preview ----
(function () {
  const form = document.getElementById("detailsform");
  if (!form) return;
  let timer = null;

  function refresh() {
    const data = {};
    new FormData(form).forEach(function (v, k) { data[k] = v; });
    fetch(form.dataset.previewUrl, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
    }).then(function (r) { return r.json(); }).then(function (c) {
      document.getElementById("pv_block").textContent = c.buyer_block;
      document.getElementById("pv_inline").textContent = c.buyer_inline;
      document.getElementById("pv_bid").textContent = c.bid_number;
      document.getElementById("pv_bid_date").textContent = c.bid_date;
      document.getElementById("pv_cat").textContent = c.category;
      document.getElementById("pv_filing").textContent = c.filing_date;
      document.getElementById("pv_letter").textContent = c.letter;
    }).catch(function () { /* preview is optional */ });
  }
  form.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(refresh, 250); });

  const hint = document.getElementById("usehint");
  if (hint) hint.addEventListener("click", function () {
    document.getElementById("line3").value = hint.dataset.text; refresh();
  });
})();

// ---- Generate page: show a "working" overlay while documents are made ----
(function () {
  const form = document.getElementById("genform");
  if (!form) return;
  form.addEventListener("submit", function () {
    document.getElementById("busy").hidden = false;
    form.querySelector("button").disabled = true;
  });
})();
