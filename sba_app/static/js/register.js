(function () {
  'use strict';

  document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('revealed'); });

  var DEFAULT_PLAN = 'sin_plan';
  var FORM_STORAGE_KEY = 'sba_reg_form';

  var form = document.getElementById('form-registro');
  if (!form) return;

  var params = new URLSearchParams(window.location.search);
  var selectedPlan = normalizePlan(params.get('plan'));

  // Max digit count per country prefix
  var PREFIX_LENGTHS = {
    '+34': 9, '+1': 10, '+44': 10, '+33': 9, '+49': 11,
    '+39': 10, '+351': 9, '+52': 10, '+54': 10, '+57': 10,
    '+56': 9, '+51': 9,
  };

  // ── Eye toggle ──────────────────────────────────────────
  (function initEye() {
    var btn = document.getElementById('btn-eye-reg');
    var inp = document.getElementById('password');
    if (!btn || !inp) return;
    btn.addEventListener('click', function () {
      var show = inp.type === 'password';
      inp.type = show ? 'text' : 'password';
      // swap icon: crossed-eye when visible, open eye when hidden
      btn.querySelector('svg').innerHTML = show
        ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>'
        : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    });
  })();

  // ── Live password requirements ───────────────────────────
  (function initPwdReqs() {
    var pwdInput = document.getElementById('password');
    var reqs = document.getElementById('pwd-requirements');
    if (!pwdInput || !reqs) return;

    function setReq(id, pass) {
      var el = document.getElementById(id);
      if (!el) return;
      el.classList.toggle('ok', pass);
      var svg = el.querySelector('svg');
      if (!svg) return;
      svg.innerHTML = pass
        ? '<circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/>'
        : '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>';
    }

    pwdInput.addEventListener('input', function () {
      var v = this.value;
      reqs.classList.add('visible');
      setReq('req-length', v.length >= 10);
      setReq('req-upper',  /[A-Z]/.test(v));
      setReq('req-lower',  /[a-z]/.test(v));
      setReq('req-digit',  /\d/.test(v));
    });
  })();

  // ── Phone prefix ─────────────────────────────────────────
  function updateDigitsMaxLength(prefix) {
    var digitsEl = form.querySelector('#phone-digits');
    if (!digitsEl) return;
    digitsEl.maxLength = PREFIX_LENGTHS[prefix] || 15;
  }

  var prefixSelect = form.querySelector('#phone-prefix');
  if (prefixSelect) {
    prefixSelect.addEventListener('change', function () {
      updateDigitsMaxLength(this.value);
    });
    updateDigitsMaxLength(prefixSelect.value);
  }

  // ── Restore saved form data after plan redirect ───────────
  (function restoreForm() {
    var saved = sessionStorage.getItem(FORM_STORAGE_KEY);
    if (!saved) return;
    try {
      var data = JSON.parse(saved);
      var nameEl      = form.querySelector('#name');
      var apellidosEl = form.querySelector('#apellidos');
      var emailEl     = form.querySelector('#email');
      var prefixEl    = form.querySelector('#phone-prefix');
      var digitsEl    = form.querySelector('#phone-digits');
      if (nameEl      && data.nombre)    nameEl.value      = data.nombre;
      if (apellidosEl && data.apellidos) apellidosEl.value = data.apellidos;
      if (emailEl     && data.email)     emailEl.value     = data.email;
      if (prefixEl    && data.prefix) {
        prefixEl.value = data.prefix;
        updateDigitsMaxLength(data.prefix);
      }
      if (digitsEl && data.digits) digitsEl.value = data.digits;
    } catch (e) {}
  })();

  // ── Helpers ───────────────────────────────────────────────
  function isValidEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,160}$/.test(String(v || '')); }
  function isValidPassword(v) {
    var p = String(v || '');
    return p.length >= 10 && p.length <= 256 && /[a-z]/.test(p) && /[A-Z]/.test(p) && /\d/.test(p);
  }
  function normalizePlan(v) {
    var allowed = ['starter', 'lite', 'smart', 'power', 'ultra'];
    var p = String(v || '').trim().toLowerCase();
    return allowed.indexOf(p) !== -1 ? p : DEFAULT_PLAN;
  }
  function showError(msg) {
    var box = document.getElementById('registro-error');
    if (box) { box.textContent = msg; box.style.display = 'block'; }
  }
  function clearError() {
    var box = document.getElementById('registro-error');
    if (box) { box.textContent = ''; box.style.display = 'none'; }
  }
  function setLoading(loading) {
    var btn = form.querySelector('.auth-form-submit');
    var label = btn ? btn.querySelector('span') : null;
    if (btn) btn.disabled = loading;
    if (label) label.textContent = loading ? 'Creando cuenta...' : 'Registrarme gratis';
  }

  // ── Submit ────────────────────────────────────────────────
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    var googleToken = (document.getElementById('google-access-token-field') || {}).value || '';
    var isGoogleMode = !!googleToken;

    var nombre    = ((form.querySelector('#name')      || {}).value || '').trim().slice(0, 80);
    var apellidos = ((form.querySelector('#apellidos') || {}).value || '').trim().slice(0, 120);
    var prefix    = ((form.querySelector('#phone-prefix') || {}).value || '+34').trim();
    var digits    = ((form.querySelector('#phone-digits') || {}).value || '').replace(/\D/g, '');
    var telefono  = (prefix + digits).slice(0, 30);
    var email     = ((form.querySelector('#email')    || {}).value || '').trim().toLowerCase();
    var password  = isGoogleMode ? '' : ((form.querySelector('#password') || {}).value || '');

    // Validations
    if (!nombre || nombre.length < 2) {
      showError('El nombre es obligatorio (mínimo 2 caracteres).');
      return;
    }
    if (!apellidos || apellidos.length < 2) {
      showError('Los apellidos son obligatorios (mínimo 2 caracteres).');
      return;
    }
    if (!digits || digits.length < 6) {
      showError('Introduce un número de teléfono válido (mínimo 6 dígitos).');
      return;
    }
    if (!isValidEmail(email)) {
      showError('Introduce una dirección de email válida.');
      return;
    }
    if (!isGoogleMode && !isValidPassword(password)) {
      var p = password;
      var msg = p.length < 10
        ? 'La contraseña debe tener al menos 10 caracteres.'
        : !(/[A-Z]/.test(p))
          ? 'La contraseña debe incluir al menos una letra mayúscula.'
          : !(/[a-z]/.test(p))
            ? 'La contraseña debe incluir al menos una letra minúscula.'
            : 'La contraseña debe incluir al menos un número.';
      showError(msg);
      return;
    }

    if (selectedPlan === DEFAULT_PLAN) {
      sessionStorage.setItem(FORM_STORAGE_KEY, JSON.stringify({
        nombre: nombre, apellidos: apellidos, email: email,
        prefix: prefix, digits: digits,
      }));
      window.location.assign('https://www.smartbookai.es/planes.html');
      return;
    }

    setLoading(true);

    var nombreCompleto = apellidos ? nombre + ' ' + apellidos : nombre;

    var payload = { nombre: nombreCompleto, telefono: telefono, email: email, plan: selectedPlan };
    if (isGoogleMode) {
      payload.google_access_token = googleToken;
    } else {
      payload.password = password;
    }

    fetch('/api/register/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok) {
          showError(result.data.error || 'No se pudo completar el registro. Revisa los datos e inténtalo de nuevo.');
          return;
        }
        sessionStorage.removeItem('sba_google_token');
        sessionStorage.removeItem(FORM_STORAGE_KEY);
        window.location.assign('/confirmar/?email=' + encodeURIComponent(email));
      })
      .catch(function () {
        showError('No se pudo conectar con el servidor. Inténtalo de nuevo en unos minutos.');
      })
      .finally(function () {
        setLoading(false);
      });
  });
})();
