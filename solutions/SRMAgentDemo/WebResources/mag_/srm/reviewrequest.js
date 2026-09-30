/*
 * SRM Stage 1 - Financial Review Request form logic (web resource mag_/srm/reviewrequest.js).
 *
 * Data checks and business rules for the buyer request (SRM-INT-006, SRM-INT-007, SRM-GOV-003)
 * and the color-coded status indicators (SRM-UX-001). See docs/03-model-driven-app.md.
 *
 * Choice values are resolved by label, never hard-coded. Indicator colors for choices come from
 * the option metadata (OptionMetadata.Color), which scripts/06-configure-review-request-form.py
 * sets from apps/supplier-financial-risk-review/indicator-colors.json.
 */
var SRM = window.SRM || {};

SRM.ReviewRequest = (function () {
    "use strict";

    var ENTITY = "mag_financialreviewrequest";
    var PANEL_CONTROL = "WebResource_srm_status";
    var DUNS_PATTERN = /^\d{9}$/;
    // Roles that may edit the Financial Risk Team section. Everyone else (buyers) sees it read-only.
    var REVIEWER_ROLES = ["SRM Financial Risk Reviewer", "System Administrator"];
    var REVIEWER_SECTIONS = [["tab_precheck", "sec_frt"]];
    var REQUIRED_FIELDS = ["mag_supplierid", "mag_buyername", "mag_buyeremail"];
    var EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    var COLOR_CHOICES = ["mag_gsaprecheckresult", "mag_reviewstatus", "mag_reviewpath", "mag_finalrating"];
    var REFRESH_FIELDS = ["mag_gsaprecheckresult", "mag_gsaratingexpiry", "mag_mandatoryrereview",
        "mag_gsarating", "mag_gsaratingdate", "mag_gsaremarks", "mag_reviewpath", "mag_reviewstatus",
        "mag_finalrating"];
    // Computed indicators that are not choice options use the same demo palette as indicator-colors.json.
    var COLOR = { green: "#107C10", amber: "#CA5010", red: "#D13438", grey: "#8A8886" };
    var LABEL = {
        skipNoDuns: "Skip - no DUNS",
        valid: "Valid active rating",
        expired: "Rating expired",
        noMatch: "No matching supplier",
        fullReview: "Full Review",
        notStarted: "Not Started"
    };
    var NOTE = {
        dunsFormat: "srm_duns_format",
        dunsMismatch: "srm_duns_mismatch",
        dunsMissing: "srm_duns_missing",
        supplierCheck: "srm_supplier_check",
        noDunsConflict: "srm_no_duns_conflict",
        noDuns: "srm_banner_noduns",
        reuse: "srm_banner_reuse",
        expired: "srm_banner_expired",
        reReview: "srm_banner_rereview",
        noMatch: "srm_banner_nomatch",
        incompleteGsa: "srm_banner_incomplete_gsa",
        saveBlocked: "srm_banner_save_blocked"
    };

    var optionColors = null;
    var supplier = { id: null, duns: null, hasDuns: null, loaded: true, error: null };

    function attr(fc, name) {
        return fc.getAttribute(name);
    }

    function value(fc, name) {
        var a = attr(fc, name);
        return a ? a.getValue() : null;
    }

    function selectedLabel(fc, name) {
        var a = attr(fc, name);
        return a && a.getValue() !== null ? a.getText() : null;
    }

    function setValue(fc, name, v) {
        var a = attr(fc, name);
        if (a && a.getValue() !== v) {
            a.setValue(v);
            // Some of these fields are read-only on the form; submit them anyway.
            a.setSubmitMode("always");
        }
    }

    function setChoiceByLabel(fc, name, label) {
        var a = attr(fc, name);
        if (!a) {
            return;
        }
        var match = (a.getOptions() || []).filter(function (o) { return o.text === label; })[0];
        if (match) {
            setValue(fc, name, match.value);
        }
    }

    function forEachControl(fc, name, action) {
        var a = attr(fc, name);
        if (a) {
            a.controls.forEach(action);
        }
    }

    function normaliseDuns(raw) {
        // D&B numbers are often written as 12-345-6789; store digits only.
        return raw ? String(raw).replace(/[\s-]/g, "") : raw;
    }

    function today() {
        var d = new Date();
        d.setHours(0, 0, 0, 0);
        return d;
    }

    function formatDate(d) {
        return d ? d.toLocaleDateString() : "";
    }

    function isReviewer() {
        var found = false;
        Xrm.Utility.getGlobalContext().userSettings.roles.forEach(function (role) {
            if (REVIEWER_ROLES.indexOf(role.name) >= 0) {
                found = true;
            }
        });
        return found;
    }

    // ---- data checks -------------------------------------------------------------------------

    function dunsState(fc) {
        var lookup = value(fc, "mag_supplierid");
        if (!lookup || !lookup.length) {
            return { code: "supplierMissing" };
        }
        var supplierId = lookup[0].id.replace(/[{}]/g, "");
        if (supplier.id !== supplierId || !supplier.loaded) {
            return { code: "supplierLoading" };
        }
        if (supplier.error) {
            return { code: "supplierUnavailable" };
        }
        if (value(fc, "mag_noduns") === true && supplier.duns) {
            return { code: "noDunsHasDuns", supplierDuns: supplier.duns };
        }
        var duns = value(fc, "mag_dunsnumber");
        if (value(fc, "mag_noduns") === true) {
            return { code: "noDuns" };
        }
        if (!duns) {
            return { code: "missing" };
        }
        if (!DUNS_PATTERN.test(duns)) {
            return { code: "format", duns: duns };
        }
        if (supplier.duns && supplier.duns !== duns) {
            return { code: "mismatch", duns: duns, supplierDuns: supplier.duns };
        }
        return { code: "ok", duns: duns };
    }

    // Field notifications block saving. "missing" and "supplierMissing" are raised only on save so a
    // new form starts quiet.
    function validate(fc, onSave) {
        var state = dunsState(fc);
        var dunsMessage = null;
        var dunsNotification = null;
        if (state.code === "format") {
            dunsMessage = "DUNS must be exactly 9 digits.";
            dunsNotification = NOTE.dunsFormat;
        } else if (state.code === "mismatch") {
            dunsMessage = "DUNS does not match the selected supplier (" + state.supplierDuns +
                "). Correct the DUNS or pick the right supplier.";
            dunsNotification = NOTE.dunsMismatch;
        } else if (state.code === "missing" && onSave) {
            dunsMessage = "Enter the supplier's 9-digit DUNS or tick 'No DUNS / DUNS applying'.";
            dunsNotification = NOTE.dunsMissing;
        } else if (state.code === "supplierMissing" && onSave) {
            dunsMessage = "Select a supplier.";
            dunsNotification = NOTE.supplierCheck;
        } else if (state.code === "supplierLoading") {
            dunsMessage = "Wait while the selected supplier's DUNS is checked.";
            dunsNotification = NOTE.supplierCheck;
        } else if (state.code === "supplierUnavailable") {
            dunsMessage = "The selected supplier could not be checked. Retry the supplier lookup before saving.";
            dunsNotification = NOTE.supplierCheck;
        } else if (state.code === "noDunsHasDuns") {
            dunsMessage = "The selected supplier has DUNS " + state.supplierDuns +
                ". Untick No DUNS / DUNS applying to use its GSA pre-check.";
            dunsNotification = NOTE.noDunsConflict;
        }
        forEachControl(fc, "mag_dunsnumber", function (c) {
            c.clearNotification(NOTE.dunsFormat);
            c.clearNotification(NOTE.dunsMismatch);
            c.clearNotification(NOTE.dunsMissing);
            c.clearNotification(NOTE.supplierCheck);
            c.clearNotification(NOTE.noDunsConflict);
            if (dunsMessage && state.code !== "noDunsHasDuns") {
                c.setNotification(dunsMessage, dunsNotification);
            }
        });
        forEachControl(fc, "mag_noduns", function (c) {
            c.clearNotification(NOTE.noDunsConflict);
            if (state.code === "noDunsHasDuns") {
                c.setNotification(dunsMessage, NOTE.noDunsConflict);
            }
        });
        forEachControl(fc, "mag_buyeremail", function (c) {
            c.clearNotification("srm_buyer_email");
            var email = value(fc, "mag_buyeremail");
            if (email && !EMAIL_PATTERN.test(email)) {
                c.setNotification("Enter a valid buyer email address.", "srm_buyer_email");
            } else if (onSave && !email) {
                c.setNotification("Buyer Email is required for review notifications.", "srm_buyer_email");
            }
        });
        forEachControl(fc, "mag_buyername", function (c) {
            c.clearNotification("srm_buyer_name");
            if (onSave && !value(fc, "mag_buyername")) {
                c.setNotification("Buyer Name is required.", "srm_buyer_name");
            }
        });
        return state;
    }

    // ---- business rules ----------------------------------------------------------------------

    // Slide 3: No DUNS disables the GSA pre-check and sends the request straight to the full review.
    function applyNoDunsRule(fc, userChange) {
        var noDuns = value(fc, "mag_noduns") === true;
        forEachControl(fc, "mag_dunsnumber", function (c) {
            c.setDisabled(noDuns);
        });
        if (noDuns) {
            setValue(fc, "mag_dunsnumber", null);
            setChoiceByLabel(fc, "mag_gsaprecheckresult", LABEL.skipNoDuns);
            setChoiceByLabel(fc, "mag_reviewpath", LABEL.fullReview);
            if (value(fc, "mag_reviewstatus") === null) {
                setChoiceByLabel(fc, "mag_reviewstatus", LABEL.notStarted);
            }
        } else if (userChange && selectedLabel(fc, "mag_gsaprecheckresult") === LABEL.skipNoDuns) {
            // Undo the bypass; the GSA pre-check derives a new result once a DUNS is entered.
            setValue(fc, "mag_gsaprecheckresult", null);
            if (selectedLabel(fc, "mag_reviewpath") === LABEL.fullReview) {
                setValue(fc, "mag_reviewpath", null);
            }
        }
    }

    function missingGsaFields(fc) {
        var missing = [];
        if (!value(fc, "mag_gsarating")) { missing.push("rating"); }
        if (!value(fc, "mag_gsaratingdate")) { missing.push("rating date"); }
        if (!value(fc, "mag_gsaremarks")) { missing.push("remarks"); }
        if (!value(fc, "mag_gsaratingexpiry")) { missing.push("expiry date"); }
        return missing;
    }

    function gsaReuseReady(fc) {
        var expiry = value(fc, "mag_gsaratingexpiry");
        return selectedLabel(fc, "mag_gsaprecheckresult") === LABEL.valid &&
            missingGsaFields(fc).length === 0 &&
            !!expiry && expiry >= today() &&
            value(fc, "mag_mandatoryrereview") === false;
    }

    function applyGsaRoutingRule(fc) {
        var result = selectedLabel(fc, "mag_gsaprecheckresult");
        var noDuns = value(fc, "mag_noduns") === true;
        // Quick Create has no GSA detail fields; do not override a server/automation decision from
        // the incomplete field set available on this compact form.
        if (fc.ui.getFormType() === 1 && result === LABEL.valid && !noDuns) {
            return;
        }
        if (!noDuns && selectedLabel(fc, "mag_reviewpath") === "Coface Fast-Track") {
            // Preserve the route selected by the later Coface automation.
            return;
        }
        if (noDuns ||
            result === LABEL.expired ||
            result === LABEL.noMatch ||
            result === LABEL.skipNoDuns ||
            (result === LABEL.valid && !gsaReuseReady(fc))) {
            setChoiceByLabel(fc, "mag_reviewpath", LABEL.fullReview);
        } else if (result === LABEL.valid && gsaReuseReady(fc)) {
            setChoiceByLabel(fc, "mag_reviewpath", "GSA Reuse");
        }
    }

    function applyRoleLocks(fc) {
        if (isReviewer()) {
            return;
        }
        REVIEWER_SECTIONS.forEach(function (path) {
            var tab = fc.ui.tabs.get(path[0]);
            var section = tab && tab.sections.get(path[1]);
            if (section) {
                section.controls.forEach(function (c) {
                    if (c.setDisabled) {
                        c.setDisabled(true);
                    }
                });
            }
        });
    }

    function loadSupplier(fc, applyDefaults) {
        var lookup = value(fc, "mag_supplierid");
        if (!lookup || !lookup.length) {
            supplier = { id: null, duns: null, hasDuns: null, loaded: true, error: null };
            return Promise.resolve();
        }
        var id = lookup[0].id.replace(/[{}]/g, "");
        supplier = { id: id, duns: null, hasDuns: null, loaded: false, error: null };
        return Xrm.WebApi.retrieveRecord("mag_supplier", id, "?$select=mag_duns,mag_hasduns").then(function (row) {
            // Ignore a stale response if the user changed suppliers while the request was in flight.
            var selected = value(fc, "mag_supplierid");
            if (!selected || selected[0].id.replace(/[{}]/g, "") !== id) {
                return;
            }
            supplier = { id: id, duns: normaliseDuns(row.mag_duns) || null, hasDuns: row.mag_hasduns, loaded: true, error: null };
            if (!applyDefaults) {
                return;
            }
            // Default the request's DUNS / No DUNS from the supplier master when the buyer has not set them.
            if (supplier.duns && !value(fc, "mag_dunsnumber") && value(fc, "mag_noduns") !== true) {
                setValue(fc, "mag_dunsnumber", supplier.duns);
            } else if (!supplier.duns && supplier.hasDuns === false && !value(fc, "mag_dunsnumber")) {
                setValue(fc, "mag_noduns", true);
                applyNoDunsRule(fc, true);
            }
        }, function (error) {
            var selected = value(fc, "mag_supplierid");
            if (selected && selected[0].id.replace(/[{}]/g, "") === id) {
                supplier = { id: id, duns: null, hasDuns: null, loaded: true, error: error };
                console.error("SRM: could not read the supplier DUNS; save is blocked", error && error.message);
            }
        });
    }

    // ---- indicators --------------------------------------------------------------------------

    function loadOptionColors() {
        if (optionColors) {
            return Promise.resolve(optionColors);
        }
        var filter = COLOR_CHOICES.map(function (n) { return "LogicalName eq '" + n + "'"; }).join(" or ");
        var url = Xrm.Utility.getGlobalContext().getClientUrl() + "/api/data/v9.2/EntityDefinitions(LogicalName='" +
            ENTITY + "')/Attributes/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=LogicalName&$filter=" +
            encodeURIComponent(filter) + "&$expand=OptionSet($select=Options)";
        return fetch(url, {
            credentials: "same-origin",
            headers: { Accept: "application/json", "OData-Version": "4.0", "OData-MaxVersion": "4.0" }
        })
            .then(function (r) { return r.ok ? r.json() : { value: [] }; })
            .then(function (body) {
                optionColors = {};
                (body.value || []).forEach(function (a) {
                    optionColors[a.LogicalName] = {};
                    a.OptionSet.Options.forEach(function (o) {
                        optionColors[a.LogicalName][o.Value] = o.Color;
                    });
                });
                return optionColors;
            })
            .catch(function () {
                optionColors = {};
                return optionColors;
            });
    }

    function choiceIndicator(fc, name, title, emptyLabel) {
        var a = attr(fc, name);
        if (!a) {
            return null;
        }
        var v = a.getValue();
        if (v === null) {
            return { title: title, label: emptyLabel, color: COLOR.grey };
        }
        var colors = (optionColors && optionColors[name]) || {};
        return { title: title, label: a.getText(), color: colors[v] || COLOR.grey };
    }

    function buildModel(fc, state) {
        var items = [];
        var duns = {
            ok: { label: "DUNS " + state.duns, color: COLOR.green },
            noDuns: { label: "No DUNS / applying", color: COLOR.grey, detail: "GSA pre-check bypassed" },
            missing: { label: "Missing", color: COLOR.red, detail: "Enter DUNS or tick No DUNS" },
            format: { label: "Invalid format", color: COLOR.red, detail: "9 digits required" },
            mismatch: { label: "Supplier mismatch", color: COLOR.red, detail: "Supplier DUNS " + state.supplierDuns },
            noDunsHasDuns: { label: "Invalid No DUNS selection", color: COLOR.red, detail: "Supplier DUNS " + state.supplierDuns },
            supplierMissing: { label: "Supplier required", color: COLOR.red },
            supplierLoading: { label: "Checking supplier...", color: COLOR.grey },
            supplierUnavailable: { label: "Supplier check failed", color: COLOR.red, detail: "Retry before saving" }
        }[state.code];
        items.push({ title: "DUNS check", label: duns.label, color: duns.color, detail: duns.detail });
        items.push(choiceIndicator(fc, "mag_gsaprecheckresult", "GSA pre-check", "Pending"));
        if (selectedLabel(fc, "mag_gsaprecheckresult") === LABEL.valid) {
            var missingGsa = fc.ui.getFormType() === 1 ? [] : missingGsaFields(fc);
            items.push(missingGsa.length
                ? { title: "GSA rating details", label: "Incomplete", color: COLOR.red, detail: "Missing " + missingGsa.join(", ") }
                : { title: "GSA rating details", label: "Complete", color: COLOR.green });
        }
        if (attr(fc, "mag_gsaratingexpiry")) {
            var expiry = value(fc, "mag_gsaratingexpiry");
            if (!expiry) {
                items.push({ title: "GSA rating validity", label: "Expiry date missing", color: COLOR.amber });
            } else if (expiry >= today()) {
                items.push({ title: "GSA rating validity", label: "Valid", color: COLOR.green, detail: "Until " + formatDate(expiry) });
            } else {
                items.push({ title: "GSA rating validity", label: "Expired", color: COLOR.amber, detail: "On " + formatDate(expiry) });
            }
        }
        if (attr(fc, "mag_mandatoryrereview")) {
            items.push(value(fc, "mag_mandatoryrereview") === true
                ? { title: "Mandatory re-review", label: "Triggered", color: COLOR.amber, detail: "GSA reuse not permitted" }
                : { title: "Mandatory re-review", label: "Not triggered", color: COLOR.green });
        }
        items.push(choiceIndicator(fc, "mag_reviewpath", "Review path", "Not determined"));
        items.push(choiceIndicator(fc, "mag_reviewstatus", "Review status", "Not set"));
        var rating = choiceIndicator(fc, "mag_finalrating", "Final rating", "Pending reviewer");
        if (rating) {
            rating.detail = "Human reviewer decision";
            items.push(rating);
        }
        return { items: items.filter(function (i) { return i; }) };
    }

    function setBanner(fc, on, message, level, id) {
        if (on) {
            fc.ui.setFormNotification(message, level, id);
        } else {
            fc.ui.clearFormNotification(id);
        }
    }

    function updateBanners(fc, state) {
        var precheck = selectedLabel(fc, "mag_gsaprecheckresult");
        var expiry = value(fc, "mag_gsaratingexpiry");
        var expired = !!expiry && expiry < today();
        var reReview = value(fc, "mag_mandatoryrereview") === true;
        setBanner(fc, state.code === "noDuns" || state.code === "noDunsHasDuns",
            "No DUNS / DUNS applying: the GSA pre-check is bypassed and this request goes to the full review.",
            "WARNING", NOTE.noDuns);
        setBanner(fc, precheck === LABEL.valid && !expired && !reReview && gsaReuseReady(fc),
            "A valid GSA rating exists for this DUNS" + (expiry ? " (until " + formatDate(expiry) + ")" : "") +
            ". The request qualifies for GSA reuse; no new financial review is needed.",
            "INFO", NOTE.reuse);
        setBanner(fc, precheck === LABEL.expired || (precheck === LABEL.valid && expired),
            "The GSA rating has expired" + (expiry ? " (" + formatDate(expiry) + ")" : "") + ". A full review is required.",
            "WARNING", NOTE.expired);
        setBanner(fc, reReview,
            "Mandatory re-review triggered: the existing GSA rating cannot be reused. A full review is required.",
            "WARNING", NOTE.reReview);
        setBanner(fc, precheck === LABEL.noMatch,
            "No matching supplier record found in GSA for this DUNS. A full review is required.",
            "WARNING", NOTE.noMatch);
        var missingGsa = missingGsaFields(fc);
        setBanner(fc, precheck === LABEL.valid && !reReview && !expired && missingGsa.length > 0,
            "The GSA result says the rating is active, but " + missingGsa.join(", ") +
            " " + (missingGsa.length === 1 ? "is" : "are") + " missing. Reuse is not confirmed; this request is routed to Full Review.",
            "WARNING", NOTE.incompleteGsa);
    }

    // On form load the panel control and its iframe can register after onLoad has run, and the
    // platform may reload the iframe later (e.g. when Quick Create opens). Pushes retry until the
    // control and the panel script are ready; each model carries a sequence number so a late retry
    // never overwrites a newer model. The shown model is also published on the app window, keyed by
    // record, so a reloaded panel can pull it. Forms without the panel (Quick Create) never find the
    // control and never replace the model.
    var PANEL_RETRIES = 40;
    var PANEL_RETRY_MS = 500;
    var modelSeq = 0;
    var shownSeq = 0;

    function publishModel(fc, model) {
        try {
            window.top.SRMReviewStatus = { recordId: fc.data.entity.getId(), model: model };
        } catch (e) {
            // The panel still receives pushes; only reload recovery is unavailable.
        }
    }

    function pushToPanel(fc, model, attempt) {
        var retry = function () {
            if (attempt < PANEL_RETRIES) {
                setTimeout(function () { pushToPanel(fc, model, attempt + 1); }, PANEL_RETRY_MS);
            }
        };
        if (shownSeq > model.seq) {
            return;
        }
        var control = fc.getControl(PANEL_CONTROL);
        if (!control || !control.getContentWindow) {
            retry();
            return;
        }
        if (shownSeq < model.seq) {
            shownSeq = model.seq;
            publishModel(fc, model);
        }
        control.getContentWindow().then(function (win) {
            if (win && win.SRMStatus) {
                win.SRMStatus.render(model);
            } else {
                retry();
            }
        }, retry);
    }

    function refresh(fc) {
        var state = validate(fc, false);
        applyGsaRoutingRule(fc);
        updateBanners(fc, state);
        var seq = ++modelSeq;
        return loadOptionColors().then(function () {
            var model = buildModel(fc, state);
            model.seq = seq;
            pushToPanel(fc, model, 0);
        });
    }

    // ---- event handlers ----------------------------------------------------------------------

    function onDunsChange(context) {
        var fc = context.getFormContext();
        var a = attr(fc, "mag_dunsnumber");
        var normalised = normaliseDuns(a.getValue());
        if (normalised !== a.getValue()) {
            a.setValue(normalised);
        }
        if (normalised && value(fc, "mag_noduns") === true) {
            setValue(fc, "mag_noduns", false);
            applyNoDunsRule(fc, true);
        }
        refresh(fc);
    }

    function onNoDunsChange(context) {
        var fc = context.getFormContext();
        applyNoDunsRule(fc, true);
        refresh(fc);
    }

    function onSupplierChange(context) {
        var fc = context.getFormContext();
        loadSupplier(fc, true).then(function () { refresh(fc); });
    }

    function onFieldChange(context) {
        refresh(context.getFormContext());
    }

    function onSave(context) {
        var fc = context.getFormContext();
        var state = validate(fc, true);
        var blocked = [ "missing", "format", "mismatch", "supplierMissing", "supplierLoading",
            "supplierUnavailable", "noDunsHasDuns" ].indexOf(state.code) >= 0 ||
            !value(fc, "mag_buyername") || !EMAIL_PATTERN.test(value(fc, "mag_buyeremail") || "");
        setBanner(fc, blocked,
            "Cannot save: select and verify a supplier, provide a matching 9-digit DUNS or choose No DUNS only for a supplier without one, and complete Buyer Name and a valid Buyer Email.",
            "ERROR", NOTE.saveBlocked);
        if (blocked) {
            context.getEventArgs().preventDefault();
        } else if (fc.ui.getFormType() === 1 && value(fc, "mag_reviewstatus") === null) {
            // Defaulted at save, not on load, so an untouched new form is not dirty.
            setChoiceByLabel(fc, "mag_reviewstatus", LABEL.notStarted);
        }
    }

    function onLoad(context) {
        var fc = context.getFormContext();
        REQUIRED_FIELDS.forEach(function (name) {
            var a = attr(fc, name);
            if (a) {
                a.setRequiredLevel("required");
            }
        });
        var handlers = {
            mag_dunsnumber: onDunsChange,
            mag_noduns: onNoDunsChange,
            mag_supplierid: onSupplierChange
        };
        Object.keys(handlers).forEach(function (name) {
            var a = attr(fc, name);
            if (a) {
                a.addOnChange(handlers[name]);
            }
        });
        REFRESH_FIELDS.forEach(function (name) {
            var a = attr(fc, name);
            if (a) {
                a.addOnChange(onFieldChange);
            }
        });
        fc.data.entity.addOnSave(onSave);
        applyRoleLocks(fc);
        applyNoDunsRule(fc, false);
        // Defaults from the supplier apply only while creating (e.g. a request opened from a supplier).
        loadSupplier(fc, fc.ui.getFormType() === 1).then(function () { refresh(fc); });
    }

    return {
        onLoad: onLoad,
        onSave: onSave,
        onDunsChange: onDunsChange,
        onNoDunsChange: onNoDunsChange,
        onSupplierChange: onSupplierChange
    };
}());
