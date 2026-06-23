(() => {
  if (!location.pathname.startsWith('/signin')) return;

  const LOGO = '/custom-assets/mmb-logo/logo-site.png';
  const AVATAR = '/custom-assets/mmb-logo/logo-embedded-chat-avatar.png';

  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };

  const makeLogo = (className, size) => {
    const wrap = document.createElement('div');
    wrap.className = className;
    wrap.setAttribute('data-mmb-logo-patch', 'true');
    wrap.style.boxSizing = 'border-box';
    wrap.style.background = 'rgba(255,255,255,.95)';
    wrap.style.border = '1px solid rgba(214,165,77,.28)';
    wrap.style.borderRadius = '6px';
    wrap.style.display = 'flex';
    wrap.style.alignItems = 'center';
    wrap.style.justifyContent = 'center';
    wrap.style.padding = size === 'large' ? '6px' : '5px';
    wrap.style.width = size === 'large' ? '108px' : '92px';
    wrap.style.height = size === 'large' ? '48px' : '40px';
    wrap.style.boxShadow = size === 'large' ? '0 12px 36px rgba(0,0,0,.28)' : '0 1px 2px rgba(0,0,0,.08)';

    const img = document.createElement('img');
    img.src = LOGO;
    img.alt = 'MMB';
    img.decoding = 'async';
    img.style.maxWidth = '100%';
    img.style.maxHeight = '100%';
    img.style.objectFit = 'contain';
    wrap.appendChild(img);
    return wrap;
  };

  const ensureLogo = () => {
    const textBadges = Array.from(document.querySelectorAll('body div'))
      .filter((el) => visible(el) && el.textContent.trim().toLowerCase() === 'mmb');

    for (const el of textBadges) {
      if (el.querySelector('img') || el.dataset.mmbLogoPatched) continue;
      const rect = el.getBoundingClientRect();
      const large = rect.y < 100 && rect.x < window.innerWidth / 2;
      el.replaceWith(makeLogo(el.className, large ? 'large' : 'small'));
    }

    const entryTitle = Array.from(document.querySelectorAll('body div'))
      .find((el) => visible(el) && el.textContent.trim() === 'mmb 企业身份中心');
    const info = entryTitle?.parentElement;

    document.querySelectorAll('[data-mmb-entry-logo]').forEach((el) => el.remove());

    if (entryTitle && info) {
      let textWrap = info.querySelector('[data-mmb-entry-text]');
      if (!textWrap) {
        textWrap = document.createElement('div');
        textWrap.setAttribute('data-mmb-entry-text', 'true');
        textWrap.style.minWidth = '0';
        while (info.firstChild) textWrap.appendChild(info.firstChild);
      }

      const avatar = document.createElement('img');
      avatar.src = AVATAR;
      avatar.alt = 'MMB';
      avatar.setAttribute('data-mmb-entry-logo', 'true');
      avatar.decoding = 'async';
      avatar.style.width = '34px';
      avatar.style.height = '34px';
      avatar.style.flex = '0 0 34px';
      avatar.style.objectFit = 'contain';
      avatar.style.borderRadius = '8px';
      avatar.style.background = 'rgba(255,255,255,.94)';
      avatar.style.border = '1px solid rgba(214,165,77,.28)';
      avatar.style.padding = '3px';

      info.dataset.mmbEntryBlock = 'true';
      info.style.display = 'flex';
      info.style.alignItems = 'center';
      info.style.gap = '10px';
      info.style.minWidth = '0';
      info.textContent = '';
      info.appendChild(avatar);
      info.appendChild(textWrap);
    }
  };

  const run = () => requestAnimationFrame(ensureLogo);
  run();
  document.addEventListener('DOMContentLoaded', run, { once: true });
  window.addEventListener('load', run, { once: true });

  let count = 0;
  const timer = setInterval(() => {
    ensureLogo();
    count += 1;
    if (count >= 30) clearInterval(timer);
  }, 200);
})();
