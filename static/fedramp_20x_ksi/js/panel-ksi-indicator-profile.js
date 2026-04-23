/**
 * panel-ksi-indicator-profile.js — class badge toggle for the KSI profile page.
 *
 * When an indicator has class_variants, clicking a class badge in the hero
 * swaps the statement text with a fade transition.
 */

(function () {
  "use strict";

  /**
   * Render statement text, replacing **Optional:** with a styled tag.
   */
  function renderStatementInto(el, text) {
    if (text.startsWith("**Optional:**")) {
      var tag = document.createElement("span");
      tag.className = "ksi-optional-tag";
      tag.textContent = "Optional";
      el.textContent = "";
      el.appendChild(tag);
      el.appendChild(
        document.createTextNode(" " + text.replace("**Optional:** ", ""))
      );
    } else {
      el.textContent = text;
    }
  }

  function initProfile() {
    // Render **Optional:** tag on the statement text regardless of class variants.
    var statementEl = document.querySelector(".ksi-profile-statement-text");
    if (statementEl) {
      renderStatementInto(statementEl, statementEl.textContent);
    }

    var variantsEl = document.getElementById("ksi-profile-variants");
    if (!variantsEl) return;

    var variants;
    try {
      variants = JSON.parse(variantsEl.textContent);
    } catch (e) {
      return;
    }
    if (!variants) return;

    var badges = document.querySelectorAll(
      ".ksi-profile-classes .ksi-class-badge--clickable"
    );
    if (!badges.length || !statementEl) return;

    badges.forEach(function (badge) {
      badge.addEventListener("click", function () {
        var cls = badge.getAttribute("data-class");
        if (!cls || !variants[cls]) return;

        var newText = variants[cls].statement || "";

        // Update active badge styling.
        badges.forEach(function (b) {
          b.classList.remove("ksi-class-badge--active");
        });
        badge.classList.add("ksi-class-badge--active");

        // Fade transition.
        statementEl.classList.add("ksi-fade-out");
        setTimeout(function () {
          renderStatementInto(statementEl, newText);
          statementEl.classList.remove("ksi-fade-out");
          statementEl.classList.add("ksi-fade-in");
          setTimeout(function () {
            statementEl.classList.remove("ksi-fade-in");
          }, 200);
        }, 150);
      });
    });
  }

  // Bootstrap.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProfile);
  } else {
    initProfile();
  }
  document.addEventListener("htmx:afterSettle", initProfile);
})();
