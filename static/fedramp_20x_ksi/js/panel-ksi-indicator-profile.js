/**
 * panel-ksi-indicator-profile.js — class badge toggle for the KSI profile page.
 *
 * When an indicator has class_variants, clicking a class badge in the hero
 * swaps the statement text with a fade transition.
 */

(function () {
  "use strict";

  function initProfile() {
    var variantsEl = document.getElementById("ksi-profile-variants");
    if (!variantsEl) return; // No class_variants — nothing to toggle.

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
    var statementEl = document.querySelector(".ksi-profile-statement-text");
    if (!badges.length || !statementEl) return;

    /**
     * Render statement text, replacing **Optional:** with a styled tag.
     */
    function renderStatement(text) {
      if (text.startsWith("**Optional:**")) {
        var tag = document.createElement("span");
        tag.className = "ksi-optional-tag";
        tag.textContent = "Optional";
        statementEl.textContent = "";
        statementEl.appendChild(tag);
        statementEl.appendChild(
          document.createTextNode(" " + text.replace("**Optional:** ", ""))
        );
      } else {
        statementEl.textContent = text;
      }
    }

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
          renderStatement(newText);
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
