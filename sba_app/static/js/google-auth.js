(function () {
  'use strict';

  var STORAGE_KEY = 'sba_google_token';
  var clientId = (document.querySelector('meta[name="google-client-id"]') || {}).content || '';
  var isLoginPage = !!document.getElementById('form-login');
  var isRegisterPage = !!document.getElementById('form-registro');
  var btn = document.getElementById('btn-google');

  // Pre-fill register form when coming from Google
  function activateGoogleMode(credential, email, name) {
    var registerForm = document.getElementById('form-registro');
    if (!registerForm) return;

    var banner = document.getElementById('google-banner');
    var emailLabel = document.getElementById('google-email-label');
    var emailField = registerForm.querySelector('#email');
    var nameField = registerForm.querySelector('#name');
    var fieldPassword = document.getElementById('field-password');
    var existing = document.getElementById('google-access-token-field');

    if (banner) banner.style.display = 'flex';
    if (emailLabel) emailLabel.textContent = email || '';
    if (emailField) { emailField.value = email || ''; emailField.readOnly = true; }
    if (nameField && name) nameField.value = name;
    if (fieldPassword) fieldPassword.style.display = 'none';

    if (!existing) {
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.id = 'google-access-token-field';
      hidden.value = credential || '';
      registerForm.appendChild(hidden);
    } else {
      existing.value = credential || '';
    }
  }

  // Register page: restore Google mode from redirect
  if (isRegisterPage) {
    var urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('from_google') === '1') {
      var storedCred = sessionStorage.getItem(STORAGE_KEY) || '';
      activateGoogleMode(storedCred, urlParams.get('email') || '', urlParams.get('name') || '');
    }
  }

  if (!btn || !clientId) return;

  var btnOriginalHTML = btn.innerHTML;
  var googleInitialized = false;
  var fallbackRendered = false;

  function ensureInit() {
    if (googleInitialized) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleCredential,
      auto_select: false,
      cancel_on_tap_outside: true,
    });
    googleInitialized = true;
  }

  // Shows the renderButton fallback — works in all browsers, no active session required
  function showFallback() {
    var container = document.getElementById('google-fallback-container');
    if (!container) return;
    if (!fallbackRendered) {
      window.google.accounts.id.renderButton(container, {
        type: 'standard',
        size: 'large',
        text: 'signin_with',
        theme: 'outline',
        locale: 'es_ES',
        width: Math.min(btn.offsetWidth || 320, 400),
      });
      fallbackRendered = true;
    }
    container.style.display = 'flex';
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideFallback() {
    var container = document.getElementById('google-fallback-container');
    if (container) container.style.display = 'none';
  }

  function clearError() {
    var box = document.getElementById('login-error') || document.getElementById('registro-error');
    if (box) { box.textContent = ''; box.style.display = 'none'; }
  }

  btn.addEventListener('click', function () {
    if (!window.google || !window.google.accounts || !window.google.accounts.id) {
      showError('El servicio de Google no está disponible todavía. Espera un momento y vuelve a intentarlo.');
      return;
    }
    clearError();
    hideFallback();
    ensureInit();
    window.google.accounts.id.prompt(function (notification) {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        showFallback();
      }
    });
  });

  function handleCredential(response) {
    hideFallback();
    var credential = response.credential;
    if (!credential) {
      showError('No se recibió credencial de Google.');
      return;
    }
    setLoading(true);

    fetch('/api/auth/google/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ id_token: credential }),
    })
      .then(function (res) {
        return res.json().then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (result) {
        setLoading(false);
        if (!result.ok) {
          showError(result.data.error || 'Error al autenticar con Google.');
          return;
        }
        var data = result.data;
        if (data.ok) {
          window.location.assign(data.redirect || '/');
        } else if (data.action === 'register') {
          if (isLoginPage) {
            sessionStorage.setItem(STORAGE_KEY, credential);
            var p = new URLSearchParams();
            p.set('from_google', '1');
            if (data.email) p.set('email', data.email);
            if (data.name) p.set('name', data.name);
            window.location.assign('/register/?' + p.toString());
          } else if (isRegisterPage) {
            activateGoogleMode(credential, data.email || '', data.name || '');
          }
        }
      })
      .catch(function () {
        setLoading(false);
        showError('No se pudo conectar con el servidor. Inténtalo de nuevo.');
      });
  }

  function setLoading(loading) {
    btn.disabled = loading;
    btn.innerHTML = loading ? 'Conectando con Google...' : btnOriginalHTML;
  }

  function showError(msg) {
    var box = document.getElementById('login-error') || document.getElementById('registro-error');
    if (box) {
      box.textContent = msg;
      box.style.display = 'block';
    }
  }
})();
