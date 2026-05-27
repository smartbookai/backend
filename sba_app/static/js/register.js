(function () {
  'use strict';

  document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('revealed'); });

  var FRONTEND_URL = (document.querySelector('meta[name="sba-frontend"]') || {}).content || '';
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

  function updateDigitsMaxLength(prefix) {
    var digitsEl = form.querySelector('#phone-digits');
    if (!digitsEl) return;
    digitsEl.maxLength = PREFIX_LENGTHS[prefix] || 15;
  }

  // Restore form data saved before plan redirect
  (function restoreForm() {
    var saved = sessionStorage.getItem(FORM_STORAGE_KEY);
    if (!saved) return;
    try {
      var data = JSON.parse(saved);
      var nameEl = form.querySelector('#name');
      var emailEl = form.querySelector('#email');
      var prefixEl = form.querySelector('#phone-prefix');
      var digitsEl = form.querySelector('#phone-digits');
      if (nameEl && data.nombre) nameEl.value = data.nombre;
      if (emailEl && data.email) emailEl.value = data.email;
      if (prefixEl && data.prefix) {
        prefixEl.value = data.prefix;
        updateDigitsMaxLength(data.prefix);
      }
      if (digitsEl && data.digits) digitsEl.value = data.digits;
    } catch (e) {}
  })();

  // Keep maxlength in sync when prefix changes
  var prefixSelect = form.querySelector('#phone-prefix');
  if (prefixSelect) {
    prefixSelect.addEventListener('change', function () {
      updateDigitsMaxLength(this.value);
    });
    updateDigitsMaxLength(prefixSelect.value);
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

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    var googleToken = (document.getElementById('google-access-token-field') || {}).value || '';
    var isGoogleMode = !!googleToken;

    var nombre = (form.querySelector('#name') || {}).value || '';
    nombre = nombre.trim().slice(0, 80);

    var prefix = ((form.querySelector('#phone-prefix') || {}).value || '+34').trim();
    var digits = ((form.querySelector('#phone-digits') || {}).value || '').replace(/\D/g, '');
    var telefono = (prefix + digits).slice(0, 30);

    var email = ((form.querySelector('#email') || {}).value || '').trim().toLowerCase();
    var password = isGoogleMode ? '' : ((form.querySelector('#password') || {}).value || '');

    // Validations
    if (!nombre || nombre.length < 2) {
      showError('El nombre es obligatorio (mínimo 2 caracteres).');
      return;
    }
    var maxDigits = PREFIX_LENGTHS[prefix] || 15;
    if (!digits || digits.length < 6 || digits.length > maxDigits) {
      showError('Introduce un número de teléfono válido (' + maxDigits + ' dígitos para ' + prefix + ').');
      return;
    }
    if (!isValidEmail(email)) {
      showError('Introduce una dirección de email válida.');
      return;
    }
    if (!isGoogleMode && !isValidPassword(password)) {
      showError('La contraseña debe tener al menos 10 caracteres e incluir mayúscula, minúscula y número.');
      return;
    }

    if (selectedPlan === DEFAULT_PLAN) {
      sessionStorage.setItem(FORM_STORAGE_KEY, JSON.stringify({
        nombre: nombre,
        email: email,
        prefix: prefix,
        digits: digits,
      }));
      window.location.assign('/planes-publicos/');
      return;
    }

    setLoading(true);

    var payload = {
      nombre: nombre,
      telefono: telefono,
      email: email,
      plan: selectedPlan,
    };
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
