(function () {
  'use strict';

  var form = document.getElementById('form-login');
  var emailField = document.getElementById('login-email');
  var passwordField = document.getElementById('login-password');
  var submitBtn = document.getElementById('btn-login-submit');
  var submitLabel = document.getElementById('btn-login-label');
  var errorBox = document.getElementById('login-error');
  var banner = document.getElementById('login-banner');
  var eyeBtn = document.getElementById('btn-eye');

  if (new URLSearchParams(window.location.search).get('registro') === 'ok' && banner) {
    banner.style.display = 'block';
  }

  if (eyeBtn && passwordField) {
    eyeBtn.addEventListener('click', function () {
      passwordField.type = passwordField.type === 'password' ? 'text' : 'password';
    });
  }

  if (!form) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var email = (emailField ? emailField.value : '').trim().toLowerCase();
    var password = passwordField ? passwordField.value : '';

    if (!email || !password) {
      showError('Por favor, introduce tu email y contraseña.');
      return;
    }

    setLoading(true);
    clearError();

    fetch('/api/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ email: email, password: password }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          showError(result.data.error || 'Credenciales incorrectas. Revisa tu email y contraseña.');
          return;
        }
        window.location.assign(result.data.redirect || '/');
      })
      .catch(function () {
        showError('No se pudo conectar con el servidor. Inténtalo de nuevo en unos minutos.');
      })
      .finally(function () {
        setLoading(false);
      });
  });

  function setLoading(loading) {
    if (submitBtn) submitBtn.disabled = loading;
    if (submitLabel) submitLabel.textContent = loading ? 'Entrando...' : 'Iniciar sesión';
  }

  function showError(msg) {
    if (errorBox) {
      errorBox.textContent = msg;
      errorBox.style.display = 'block';
    }
  }

  function clearError() {
    if (errorBox) {
      errorBox.textContent = '';
      errorBox.style.display = 'none';
    }
  }
})();
