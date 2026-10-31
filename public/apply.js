const form = document.getElementById('apply-form');
const done = document.getElementById('apply-done');
const resume = form.elements.resume;
const drop = resume.closest('.apply-drop');
const title = document.getElementById('resume-title');
const meta = document.getElementById('resume-meta');
const captchaInput = form.elements.captcha;
const captchaToken = form.elements.captcha_token;
const captchaQ = document.getElementById('captcha-q');
const button = form.querySelector('.apply-submit');
const btnLabel = button.querySelector('.apply-submit-label');
const btnWait = button.querySelector('.apply-submit-wait');
const roleBtn = document.getElementById('role-btn');
const roleMenu = document.getElementById('role-menu');
const roleInput = form.elements.role;
const roleValue = roleBtn.querySelector('.apply-role-value');

function closeRole() {
  roleMenu.hidden = true;
  roleBtn.setAttribute('aria-expanded', 'false');
}

roleBtn.addEventListener('click', () => {
  const open = roleMenu.hidden;
  roleMenu.hidden = !open;
  roleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
});

roleMenu.addEventListener('click', (e) => {
  const item = e.target.closest('li');
  if (!item || item.classList.contains('is-filled')) return;
  roleMenu.querySelectorAll('[aria-selected="true"]').forEach((el) => el.setAttribute('aria-selected', 'false'));
  item.setAttribute('aria-selected', 'true');
  roleInput.value = item.dataset.value;
  roleValue.textContent = item.dataset.value;
  closeRole();
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.apply-role')) closeRole();
});

function showResume(file) {
  if (!file) {
    drop.classList.remove('is-ready');
    title.innerHTML = 'Drop your resume here, or <em>browse</em>';
    meta.textContent = 'PDF preferred · DOC / DOCX ok · Max 5 MB';
    return;
  }
  drop.classList.add('is-ready');
  title.textContent = file.name;
  meta.textContent = `${(file.size / 1024).toFixed(file.size > 1024 * 100 ? 0 : 1)} KB ready to send`;
}

function setCaptcha(data) {
  captchaToken.value = data.token;
  captchaQ.textContent = `What is ${data.a} + ${data.b}?`;
  captchaInput.value = '';
}

async function loadCaptcha() {
  const res = await fetch('/apply-captcha', { cache: 'no-store' });
  if (!res.ok) throw new Error('captcha');
  setCaptcha(await res.json());
}

resume.addEventListener('change', () => {
  resume.setCustomValidity('');
  showResume(resume.files[0]);
});

['dragenter', 'dragover'].forEach((type) => {
  drop.addEventListener(type, (e) => {
    e.preventDefault();
    drop.classList.add('is-drag');
  });
});
['dragleave', 'drop'].forEach((type) => {
  drop.addEventListener(type, (e) => {
    e.preventDefault();
    drop.classList.remove('is-drag');
  });
});
drop.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files?.[0];
  if (!file) return;
  const dt = new DataTransfer();
  dt.items.add(file);
  resume.files = dt.files;
  resume.setCustomValidity('');
  showResume(file);
});

if (captchaToken.value && captchaQ.dataset.ready === '1') {
  // server already injected the challenge
} else {
  loadCaptcha().catch(() => {
    captchaQ.textContent = 'Could not load check. Refresh the page.';
  });
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!form.reportValidity()) return;
  const file = resume.files[0];
  if (!file) {
    resume.setCustomValidity('Attach your resume');
    resume.reportValidity();
    return;
  }
  if (file.size > 5_000_000) {
    resume.setCustomValidity('Resume must be 5 MB or smaller');
    resume.reportValidity();
    return;
  }
  if (!captchaToken.value || !String(captchaInput.value || '').trim()) {
    captchaInput.setCustomValidity('Solve the quick check');
    captchaInput.reportValidity();
    return;
  }
  captchaInput.setCustomValidity('');
  resume.setCustomValidity('');
  button.disabled = true;
  button.classList.add('is-sending');
  btnLabel.hidden = true;
  btnWait.hidden = false;
  try {
    const res = await fetch('/apply', { method: 'POST', body: new FormData(form) });
    if (res.status === 429) throw new Error('rate');
    if (!res.ok) throw new Error('send');
    form.hidden = true;
    done.hidden = false;
  } catch (err) {
    button.disabled = false;
    button.classList.remove('is-sending');
    btnLabel.hidden = false;
    btnWait.hidden = true;
    btnLabel.textContent = err.message === 'rate'
      ? 'Too many tries. Wait a bit.'
      : "Couldn't send. Try again";
    loadCaptcha().catch(() => {
      captchaQ.textContent = 'Could not load check. Refresh the page.';
    });
  }
});
