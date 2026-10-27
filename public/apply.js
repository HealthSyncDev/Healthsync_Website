const form = document.getElementById('apply-form');
const done = document.getElementById('apply-done');
const resume = form.elements.resume;
const drop = resume.closest('.apply-drop');
const title = document.getElementById('resume-title');
const meta = document.getElementById('resume-meta');
const captchaInput = form.elements.captcha;
const captchaToken = form.elements.captcha_token;
const captchaLabel = document.getElementById('captcha-label');
const button = form.querySelector('.apply-submit');
const btnLabel = button.querySelector('.apply-submit-label');
const btnWait = button.querySelector('.apply-submit-wait');

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

async function loadCaptcha() {
  const res = await fetch('/apply-captcha');
  if (!res.ok) throw new Error('captcha');
  const data = await res.json();
  captchaToken.value = data.token;
  captchaLabel.textContent = `What is ${data.a} + ${data.b}?`;
  captchaInput.value = '';
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

loadCaptcha().catch(() => {
  captchaLabel.textContent = 'Captcha unavailable. Refresh the page.';
});

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
    loadCaptcha().catch(() => {});
  }
});
