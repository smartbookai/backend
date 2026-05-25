(function () {
  'use strict';

  var STORAGE_KEY = 'sba_google_token';
  var clientId = (document.querySelector('meta[name="google-client-id"]') || {}).content || '';
  var isLoginPage = !!document.getElementById('form-login');
  var isRegisterPage = !!document.getElementById('form-registro');
  var btn = document.getElementById('btn-google');

  // --- Pre-fill register form when coming from Google (either via redirect or button on this page) ---
  function activateGoogleMode(token, email, name) {
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
      hidden.value = token || '';
      registerForm.appendChild(hidden);
    } else {
      existing.value = token || '';
    }
  }

  // On register page: detect URL params from a Google redirect
  if (isRegisterPage) {
    var params = new URLSearchParams(window.location.search);
    if (params.get('from_google') === '1') {
      var token = sessionStorage.getItem(STORAGE_KEY) || '';
      activateGoogleMode(token, params.get('email') || '', params.get('name') || '');
    }
  }

  // --- Google button ---
  if (!btn || !clientId) return;

  var tokenClient = null;
  var btnOriginalHTML = btn.innerHTML;

  btn.addEventListener('click', function () {
    if (!window.google || !window.google.accounts || !window.google.accounts.oauth2) {
      showError('El servicio de Google no está disponible todavía. Espera un momento y vuelve a intentarlo.');
      return;
    }
    if (!tokenClient) {
      tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: 'openid email profile',
        callback: handleToken,
      });
    }
    tokenClient.requestAccessToken({ prompt: 'select_account' });
  });

  function handleToken(tokenResponse) {
    if (tokenResponse.error) {
      showError('No se pudo completar la autenticación con Google. Inténtalo de nuevo.');
      return;
    }

    var accessToken = tokenResponse.access_token;
    setLoading(true);

    fetch('/api/auth/google/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ access_token: accessToken }),
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
            sessionStorage.setItem(STORAGE_KEY, accessToken);
            var p = new URLSearchParams();
            p.set('from_google', '1');
            if (data.email) p.set('email', data.email);
            if (data.name) p.set('name', data.name);
            window.location.assign('/register/?' + p.toString());
          } else if (isRegisterPage) {
            activateGoogleMode(accessToken, data.email || '', data.name || '');
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
