const form = document.getElementById('contact-form');
const done = document.getElementById('contact-done');
const needs = [...form.querySelectorAll('input[name="need"]')];
const name = form.elements.name;
const email = form.elements.email;
const nameError = document.getElementById('name-error');
const emailError = document.getElementById('email-error');

const tidy = (value) => value.trim().replace(/\s+/g, ' ');
const okName = (value) => /^\p{L}[\p{L}'’.-]*(?:\s+\p{L}[\p{L}'’.-]*)+$/u.test(value);
const okEmail = (value) => /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/.test(value);

function show(input, el, msg) {
  input.setCustomValidity(msg);
  input.setAttribute('aria-invalid', msg ? 'true' : 'false');
  el.hidden = !msg;
  el.textContent = msg;
}

function checkFields() {
  const n = tidy(name.value);
  const m = tidy(email.value);
  show(name, nameError, !n ? 'Enter your name' : okName(n) ? '' : 'Enter a correct name');
  show(email, emailError, !m ? 'Enter your email' : okEmail(m) ? '' : 'Enter a correct email');
}

[name, email].forEach((input) => {
  input.addEventListener('blur', checkFields);
  input.addEventListener('input', () => {
    if (!nameError.hidden || !emailError.hidden) checkFields();
  });
});

needs.forEach((box) =>
  box.addEventListener('change', () => needs[0].setCustomValidity('')),
);

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  checkFields();
  if (name.validationMessage || email.validationMessage) {
    (name.validationMessage ? name : email).focus();
    return;
  }
  const picked = needs.some((box) => box.checked);
  needs[0].setCustomValidity(picked ? '' : 'Pick at least one');
  if (!form.reportValidity()) return;
  const fd = new FormData(form);
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    const res = await fetch('/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: tidy(String(fd.get('name') || '')),
        email: tidy(String(fd.get('email') || '')),
        need: fd.getAll('need'),
        brief: String(fd.get('brief') || '').trim(),
      }),
    });
    if (!res.ok) throw new Error('send');
    form.hidden = true;
    done.hidden = false;
  } catch {
    button.disabled = false;
    button.textContent = "Couldn't send — try again";
  }
});
