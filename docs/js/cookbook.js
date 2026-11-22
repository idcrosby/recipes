"use strict";

const normalize = (text) =>
  text.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

const search = document.querySelector("#recipe-search");

if (search) {
  const tools = document.querySelector(".collection-tools");
  const filters = [...tools.querySelectorAll("[data-category]")];
  const count = tools.querySelector(".result-count");
  const empty = document.querySelector(".empty-state");
  const cards = [...document.querySelectorAll(".recipe-card")].map((card) => ({
    card,
    categories: card.dataset.categories.split(" "),
    text: normalize(card.querySelector("h2").textContent + " " + card.dataset.ingredients)
  }));
  let category = "";

  function updateRecipes() {
    const terms = normalize(search.value.trim()).split(/\s+/);
    let visible = 0;

    for (const recipe of cards) {
      const matchesCategory = !category || recipe.categories.includes(category);
      const matchesSearch = terms.every((term) => recipe.text.includes(term));
      recipe.card.hidden = !(matchesCategory && matchesSearch);
      if (!recipe.card.hidden) visible += 1;
    }

    count.textContent = visible === 1 ? "1 recipe" : `${visible} recipes`;
    empty.hidden = visible !== 0;
  }

  for (const filter of filters) {
    filter.addEventListener("click", () => {
      category = filter.dataset.category;
      for (const button of filters) {
        button.setAttribute("aria-pressed", String(button === filter));
      }
      updateRecipes();
    });
  }

  search.addEventListener("input", updateRecipes);
  tools.hidden = false;
  updateRecipes();
}

const printButton = document.querySelector(".print-button");

if (printButton) {
  printButton.addEventListener("click", () => window.print());
  printButton.hidden = false;

  const items = document.querySelectorAll(".recipe-body .ingredients > li");
  for (const [index, item] of items.entries()) {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `ingredient-${index + 1}`;

    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.append(...item.childNodes);
    item.append(checkbox, label);
    item.classList.add("checkable");
  }
}
