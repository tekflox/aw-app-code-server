/*
 * iOS on-screen-keyboard suppressor for code-server.
 *
 * WHY THIS EXISTS
 * ---------------
 * On an iPhone with a Bluetooth keyboard, the native on-screen keyboard eats
 * most of the screen every time focus lands in an editable element. The
 * workspace shell (repos/aw-workspace-ui) already solves this for its own
 * fields with a global "suppress keyboard" toggle. It cannot solve it here:
 * code-server is served from `code-server.app.<apex>` while the shell is at
 * `<apex>`, so the iframe is CROSS-ORIGIN and `contentDocument` is blocked.
 * Cooperation from inside the iframe is the only option, so this script is
 * baked into the image (see container/patch-workbench.py) and talks to the
 * shell over postMessage.
 *
 * THE MECHANISM, AND WHY IT IS `readonly` AND NOT A FOCUS PROXY
 * ------------------------------------------------------------
 * aw-workspace-ui commit bc1235a proved on Frederico's actual iPhone that a
 * READONLY form control keeps the iOS keyboard down while STILL receiving
 * hardware keydown events. That single fact is what makes this design cheap:
 * we mark VS Code's own editor textarea readonly and otherwise do nothing, so
 * every VS Code keybinding — arrows, Enter, Backspace, chords, Cmd+S — keeps
 * flowing through VS Code's own untouched keydown path. We write no key
 * mapping of our own.
 *
 * A focus proxy (the shape lib/suppressedTextInput.js uses in the shell) was
 * deliberately rejected for this surface: VS Code owns focus, calls
 * `textArea.focus()` constantly and recreates the textarea per editor, so
 * shadowing focus here means chasing a moving target and reimplementing VS
 * Code's whole keybinding layer through synthetic dispatch.
 *
 * The ONLY thing `readonly` breaks is printable-character insertion, because
 * it kills the native `input` event VS Code reads from. `insertPrintable()`
 * below restores exactly that and nothing else.
 *
 * THE EditContext FORK — READ THIS BEFORE CHANGING ANYTHING
 * --------------------------------------------------------
 * Modern VS Code has TWO editor input implementations and picks between them
 * at runtime. Verified in this image's own bundle (code-server 4.135.0,
 * out/vs/workbench/workbench.web.main.internal.js):
 *
 *   - option 44 `editContext` defaults to TRUE:
 *       editContext: to(new oa(44,"editContext",!0,{...}))
 *   - the effective option 170 is:
 *       compute(o,e){ return o.editContextSupported && e.get(44) }
 *   - and `editContextSupported` is a bare capability probe:
 *       editContextSupported: typeof globalThis.EditContext == "function"
 *
 * When that is true, VS Code uses NativeEditContext, whose input host is a
 * `div.native-edit-context` — there is NO `textarea.inputarea` in the document
 * at all, and `readonly` is meaningless on a div that an EditContext has made
 * an editing host. Confirmed live in Chromium 151 against this exact
 * container: 0 `textarea.inputarea`, 1 `.native-edit-context`.
 *
 * WebKit shipped EditContext, so a current iPhone lands on that branch too and
 * the readonly mechanism would silently do nothing. So before workbench.js
 * runs we remove `globalThis.EditContext`, which makes the probe above return
 * false and forces VS Code down the textarea path. That path is not a
 * degradation — it is what VS Code used exclusively until 2024 and still what
 * every non-EditContext browser gets today.
 *
 * We only do it when it can actually be needed (see `shouldForceTextAreaPath`)
 * so a desktop code-server user, who will never suppress anything, keeps the
 * newer input path untouched.
 *
 * KNOWN TRADE-OFF: a readonly textarea cannot do IME composition, so dead-key
 * / accented input is expected to be affected while suppression is ON. This is
 * called out deliberately rather than absorbed silently — see the card.
 */
(function () {
  'use strict';

  var SHELL_MSG = 'aw:kbd-suppress';        // shell -> app, carries { on }
  var HELLO_MSG = 'aw:kbd-suppress-hello';  // app -> shell, "tell me the state"
  // Marks the elements WE made readonly, so turning suppression off never
  // clears a `readonly` that VS Code set for its own reasons (a diff editor's
  // original pane, the issue reporter, ...).
  var MARK = 'awKbdReadonly';               // dataset key -> data-aw-kbd-readonly
  // Last known suppress state, persisted on THIS origin. Read at parse time,
  // long before the shell's first message can arrive, to decide whether the
  // textarea path has to be forced on this load.
  var LAST_STATE_KEY = 'aw_kbd_suppress_last';

  // VS Code's editor textarea, and the integrated terminal's xterm helper.
  // The xterm one needs no input hook at all — xterm derives everything from
  // keydown — so it is listed separately.
  var EDITOR_SEL = 'textarea.inputarea';
  var TERMINAL_SEL = 'textarea.xterm-helper-textarea';
  var ALL_SEL = EDITOR_SEL + ',' + TERMINAL_SEL;

  var suppressed = false;

  function readLastState() {
    try { return localStorage.getItem(LAST_STATE_KEY) === '1'; } catch (e) { return false; }
  }

  function writeLastState(on) {
    try {
      if (on) localStorage.setItem(LAST_STATE_KEY, '1');
      else localStorage.removeItem(LAST_STATE_KEY);
    } catch (e) { /* private mode / storage disabled */ }
  }

  /*
   * Same gate the shell uses (isPhoneClassTouchDevice in
   * repos/aw-workspace-ui/src/lib/hardwareKeyboardBridge.js) — kept in sync by
   * hand because the two documents share no code across the origin boundary.
   */
  function isPhoneClassTouchDevice() {
    try {
      return navigator.maxTouchPoints > 1 &&
             Math.min(window.screen.width, window.screen.height) < 600;
    } catch (e) {
      return false;
    }
  }

  /*
   * Force the textarea path when suppression could plausibly be used on this
   * load: a phone-class device (where it is the whole point), or any device
   * that has had suppression on before at this origin. Everyone else keeps
   * NativeEditContext. A desktop user who turns suppression on for the first
   * time gets the textarea path on their next load of the app, not this one.
   */
  function shouldForceTextAreaPath() {
    return isPhoneClassTouchDevice() || readLastState();
  }

  if (shouldForceTextAreaPath()) {
    try { delete globalThis.EditContext; } catch (e) { /* non-configurable */ }
  }

  // Taken off the prototype because `readonly` blocks the USER, not scripts —
  // this is the same native setter React's own tests and Playwright use to
  // fill a controlled input.
  var nativeTextAreaValue = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype, 'value'
  );

  function applyOne(el, on) {
    if (!el) return;
    if (on) {
      if (el.getAttribute('readonly') === null) {
        el.setAttribute('readonly', 'true');
      }
      el.dataset[MARK] = '1';
    } else if (el.dataset[MARK] === '1') {
      el.removeAttribute('readonly');
      delete el.dataset[MARK];
    }
  }

  function applyToAll() {
    var nodes = document.querySelectorAll(ALL_SEL);
    for (var i = 0; i < nodes.length; i++) applyOne(nodes[i], suppressed);
  }

  /*
   * Restore printable-character insertion, and ONLY that.
   *
   * `readonly` stops the browser from generating the `input` event VS Code
   * reads from, so without this the editor receives every command key and no
   * text. We write the character at the caret through the native value setter
   * and dispatch the `input` event VS Code was waiting for, which is exactly
   * the sequence a real keystroke would have produced.
   */
  function insertPrintable(el, ch) {
    if (!nativeTextAreaValue || !nativeTextAreaValue.set) return;
    var start = el.selectionStart;
    var end = el.selectionEnd;
    var value = el.value;
    if (typeof start !== 'number' || typeof end !== 'number') return;
    nativeTextAreaValue.set.call(el, value.slice(0, start) + ch + value.slice(end));
    try {
      el.selectionStart = el.selectionEnd = start + ch.length;
    } catch (e) { /* detached */ }
    el.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: false,
      inputType: 'insertText',
      data: ch
    }));
  }

  /* A single printable character, as opposed to 'Enter' / 'ArrowLeft' / 'Dead'. */
  function printableChar(ev) {
    var k = ev.key;
    if (typeof k !== 'string') return null;
    // Array.from so an astral character (length 2 in UTF-16 units) still counts
    // as one, while every named key ('Enter', 'Dead', ...) does not.
    return Array.from(k).length === 1 ? k : null;
  }

  function onKeyDown(ev) {
    if (!suppressed) return;
    var el = ev.target;
    if (!el || el.tagName !== 'TEXTAREA') return;
    if (el.dataset[MARK] !== '1') return;
    // xterm builds its escape sequences straight from keydown and never reads
    // the textarea's value — writing into it would double every character.
    if (el.classList.contains('xterm-helper-textarea')) return;
    // Let every chord through untouched: they are VS Code keybindings, and
    // VS Code's own keydown path still receives them.
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    var ch = printableChar(ev);
    if (ch === null) return;
    insertPrintable(el, ch);
  }

  /*
   * VS Code actively manages this attribute: `_ensureReadOnlyAttribute()` in
   * the bundle does
   *   ...? this.textArea.setAttribute("readonly","true")
   *      : this.textArea.removeAttribute("readonly")
   * and runs it whenever editor options change, so for an editable editor it
   * REMOVES our readonly out from under us. Watching childList alone would
   * have left suppression silently decaying. Hence `attributeFilter`.
   *
   * No re-entrancy guard is needed: `applyOne` only writes when the attribute
   * is not already in the state we want, so our own writes settle in one pass.
   */
  var observer = new MutationObserver(function (mutations) {
    if (!suppressed) return;
    for (var i = 0; i < mutations.length; i++) {
      var m = mutations[i];
      if (m.type === 'attributes') {
        applyOne(m.target, true);
        continue;
      }
      for (var j = 0; j < m.addedNodes.length; j++) {
        var n = m.addedNodes[j];
        if (n.nodeType !== 1) continue;
        if (n.matches && n.matches(ALL_SEL)) applyOne(n, true);
        if (!n.querySelectorAll) continue;
        var inner = n.querySelectorAll(ALL_SEL);
        for (var k = 0; k < inner.length; k++) applyOne(inner[k], true);
      }
    }
  });

  function setSuppressed(on) {
    on = !!on;
    var changed = on !== suppressed;
    suppressed = on;
    writeLastState(on);
    applyToAll();
    if (changed && on === false) {
      // Nothing else to undo: applyToAll above already cleared every mark.
    }
  }

  /*
   * Origin validation. The apex is DERIVED, never hardcoded — this image is
   * deployed under more than one workspace slug. We are served from
   * `<app-id>.app.<apex>`; the shell that embeds us is at `<apex>`, or at
   * `www.<apex>` (its buildProxyUrl strips a leading `www.` when composing our
   * URL, so the parent can legitimately carry one while we do not).
   */
  function allowedHosts() {
    var host = location.hostname;
    var hosts = [host];
    var m = /^[^.]+\.app\.(.+)$/.exec(host);
    if (m) {
      hosts.push(m[1]);
      hosts.push('www.' + m[1]);
    }
    return hosts;
  }

  var ALLOWED = allowedHosts();

  function isTrustedOrigin(origin) {
    var u;
    try { u = new URL(origin); } catch (e) { return false; }
    if (u.protocol !== location.protocol) return false;
    return ALLOWED.indexOf(u.hostname) !== -1;
  }

  function onMessage(ev) {
    var d = ev.data;
    if (!d || typeof d !== 'object' || d.type !== SHELL_MSG) return;
    if (!isTrustedOrigin(ev.origin)) return;
    setSuppressed(d.on);
  }

  /*
   * The hello is not optional. The shell posts the current state on the
   * iframe's `onLoad`, but this script keeps running long after that — and on
   * a warm/bfcache load it can boot after `onLoad` already fired. Asking
   * removes that race.
   *
   * We still need a TARGETED origin to ask with, never '*'. `document.referrer`
   * is the exact answer when it is there, but the default
   * `strict-origin-when-cross-origin` policy can be tightened to `no-referrer`
   * by the shell at any time, which would silently cost us the hello leg. So
   * the derived apex is the fallback: we know we are at `<app-id>.app.<apex>`,
   * so the shell is at `<apex>` — and both candidates go through the same
   * `isTrustedOrigin` check. A postMessage whose target origin does not match
   * the parent is dropped by the browser, so trying both is safe.
   */
  function helloTargets() {
    var targets = [];
    try {
      if (document.referrer) {
        var r = new URL(document.referrer);
        if (isTrustedOrigin(r.origin)) targets.push(r.origin);
      }
    } catch (e) { /* opaque referrer */ }
    for (var i = 0; i < ALLOWED.length; i++) {
      var candidate = location.protocol + '//' + ALLOWED[i];
      if (candidate !== location.origin && targets.indexOf(candidate) === -1) {
        targets.push(candidate);
      }
    }
    return targets;
  }

  function sayHello() {
    // Two ways this document can be embedded: a shell <iframe> (window.parent
    // !== window), or a window.open() popup (window.opener set, parent is
    // always window itself there). Try whichever applies — both post to the
    // same set of trusted origins, so trying both when both happen to be set
    // is harmless.
    var target = window.parent !== window ? window.parent : window.opener;
    if (!target) return;
    var targets = helloTargets();
    for (var i = 0; i < targets.length; i++) {
      try {
        target.postMessage({ type: HELLO_MSG }, targets[i]);
      } catch (e) { /* parent/opener gone */ }
    }
  }

  window.addEventListener('message', onMessage);
  // Capture phase, at the document: the textarea is replaced per editor, so
  // binding to the element itself would need re-binding on every swap.
  document.addEventListener('keydown', onKeyDown, true);

  function start() {
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['readonly']
    });
    // Re-assert whatever we knew last, so a reload does not drop suppression
    // for the round-trip it takes the shell to answer our hello.
    setSuppressed(readLastState());
    sayHello();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }

  // Small surface for on-device debugging: `window.__awKbdSuppress.state()`.
  window.__awKbdSuppress = {
    state: function () {
      return {
        suppressed: suppressed,
        editContext: typeof globalThis.EditContext,
        editorTextareas: document.querySelectorAll(EDITOR_SEL).length,
        terminalTextareas: document.querySelectorAll(TERMINAL_SEL).length,
        marked: document.querySelectorAll('[data-aw-kbd-readonly]').length,
        allowedHosts: ALLOWED
      };
    },
    set: setSuppressed
  };
})();
