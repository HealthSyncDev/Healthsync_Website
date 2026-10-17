const form = document.getElementById('contact-form');
const done = document.getElementById('contact-done');
const needs = [...form.querySelectorAll('input[name="need"]')];

needs.forEach((box) =>
  box.addEventListener('change', () => needs[0].setCustomValidity('')),
);

form.addEventListener('submit', (e) => {
  const picked = needs.some((box) => box.checked);
  needs[0].setCustomValidity(picked ? '' : 'Pick at least one');
  if (!form.reportValidity()) {
    e.preventDefault();
    return;
  }
  e.preventDefault();
  const fd = new FormData(form);
  const chosen = fd.getAll('need').join(', ');
  const brief = String(fd.get('brief') || '').trim();
  const body = [
    `Name: ${fd.get('name')}`,
    `Email: ${fd.get('email')}`,
    `Needs: ${chosen}`,
    `Scope: ${fd.get('scope') || '—'}`,
    brief,
  ]
    .filter(Boolean)
    .join('\n');
  // ponytail: mailto until a form endpoint exists
  location.href = `mailto:?subject=${encodeURIComponent('HealthSync enquiry — ' + chosen)}&body=${encodeURIComponent(body)}`;
  form.hidden = true;
  done.hidden = false;
});
