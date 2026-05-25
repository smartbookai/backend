(function () {
  'use strict';

  // main.js ya no se carga aquí, así que activamos manualmente las animaciones de entrada
  document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('revealed'); });

  var FRONTEND_URL = (document.querySelector('meta[name="sba-frontend"]') || {}).content || '';
  var DEFAULT_PLAN = 'sin_plan';

  var form = document.getElementById('form-registro');
  if (!form) return;

  var params = new URLSearchParams(window.location.search);
  var selectedPlan = normalizePlan(params.get('plan'));

  // Validation helpers
  function isValidEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,160}$/.test(String(v || '')); }
  function isValidPassword(v) {
    var p = String(v || '');
    return p.length >= 8 && p.length <= 256 && /[a-z]/.test(p) && /[A-Z]/.test(p) && /\d/.test(p);
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

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    var googleToken = (document.getElementById('google-access-token-field') || {}).value || '';
    var isGoogleMode = !!googleToken;

    var nombre = (form.querySelector('#name') || {}).value || '';
    nombre = nombre.trim().slice(0, 80);
    var telefono = (form.querySelector('#phone') || {}).value || '';
    telefono = telefono.replace(/[^\d+\s().-]/g, '').slice(0, 30).trim();
    var email = ((form.querySelector('#email') || {}).value || '').trim().toLowerCase();
    var password = isGoogleMode ? '' : ((form.querySelector('#password') || {}).value || '');

    // Validation
    if (!nombre || nombre.length < 2) {
      showError('El nombre es obligatorio (mínimo 2 caracteres).');
      return;
    }
    if (!telefono || !/^[+\d\s().-]{6,30}$/.test(telefono)) {
      showError('Introduce un número de teléfono válido.');
      return;
    }
    if (!isValidEmail(email)) {
      showError('Introduce una dirección de email válida.');
      return;
    }
    if (!isGoogleMode && !isValidPassword(password)) {
      showError('La contraseña debe tener entre 8 y 256 caracteres e incluir mayúscula, minúscula y número.');
      return;
    }

    if (selectedPlan === DEFAULT_PLAN) {
      window.location.assign(FRONTEND_URL + '/planes.html');
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
