(() => {
  if (!location.pathname.startsWith('/signin')) return;

  const LOGO = '/custom-assets/mmb-logo/logo-embedded-chat-avatar.png';
  const AVATAR = '/custom-assets/mmb-logo/logo-embedded-chat-avatar.png';

  const visible = (el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };

  const styleLogoWrap = (wrap, size) => {
    wrap.setAttribute('data-mmb-logo-patch', 'true');
    wrap.style.boxSizing = 'border-box';
    wrap.style.background = 'transparent';
    wrap.style.border = '0';
    wrap.style.borderRadius = '0';
    wrap.style.display = 'flex';
    wrap.style.alignItems = 'center';
    wrap.style.justifyContent = 'center';
    wrap.style.padding = '0';
    wrap.style.width = size === 'large' ? '52px' : '40px';
    wrap.style.height = size === 'large' ? '52px' : '40px';
    wrap.style.boxShadow = 'none';
    wrap.style.backdropFilter = 'none';
  };



  const findEntryCard = () => {
    const labels = Array.from(document.querySelectorAll('body div'))
      .filter((el) => el.children.length === 0 && (el.textContent || '').trim() === '访问入口');

    for (const label of labels) {
      let node = label.parentElement;
      for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {
        const text = (node.textContent || '').replace(/\s+/g, '');
        if (text.includes('访问入口')
          && text.includes('安全在线')
          && !!node.querySelector('img[src*="logo-embedded-chat-avatar"]')) {
          return node;
        }
      }
    }

    return null;
  };

  const styleEntryIconWrap = (wrap) => {
    if (!wrap) return;
    wrap.style.background = 'transparent';
    wrap.style.border = '0';
    wrap.style.borderRadius = '0';
    wrap.style.padding = '0';
    wrap.style.boxShadow = 'none';
    wrap.style.backdropFilter = 'none';
    wrap.style.width = '40px';
    wrap.style.height = '40px';
  };

  const styleEntryCard = (info) => {
    if (!info) return;
    info.style.background = 'rgba(18,23,34,.30)';
    info.style.border = '0';
    info.style.outline = '0';
    info.style.boxShadow = 'none';
    info.style.backdropFilter = 'none';
  };


  const styleSecurityHighlights = () => {
    const labels = new Set(['企业角色校验', '工作区级隔离', '登录后审计追踪']);
    Array.from(document.querySelectorAll('body div'))
      .filter((el) => el.children.length === 0 && labels.has((el.textContent || '').trim()))
      .forEach((el) => {
        el.style.display = 'flex';
        el.style.alignItems = 'center';
        el.style.justifyContent = 'center';
        el.style.textAlign = 'center';
        el.style.minHeight = '48px';
        el.style.lineHeight = '16px';
      });
  };

  const styleLegacyEntryClasses = () => {
    Array.from(document.querySelectorAll('div[class*="bg-[#121722]/72"][class*="border-white/10"]'))
      .forEach(styleEntryCard);

    Array.from(document.querySelectorAll('div[class*="bg-[#171b24]/88"], div[class*="border-[#d6a54d]/24"]'))
      .forEach((el) => {
        if (el.querySelector('img[src*="logo-embedded-chat-avatar"]'))
          styleEntryIconWrap(el);
      });
  };

  const styleLogoImage = (img) => {
    img.src = LOGO;
    img.alt = 'MMB';
    img.decoding = 'async';
    img.style.width = '100%';
    img.style.height = '100%';
    img.style.maxWidth = '100%';
    img.style.maxHeight = '100%';
    img.style.objectFit = 'contain';
    img.style.filter = 'drop-shadow(0 8px 18px rgba(0,0,0,.22))';
  };

  const copyReplacements = new Map([
    ['企业控制台', 'AI 中台'],
    ['Dify 权限增强版', 'MMBAI 企业版'],
    ['广场啤酒企业 AI 平台', 'MMBAI 企业 AI 中台'],
    ['广场啤酒业务智能管理中枢', 'MMB AI 中台'],
    ['面向门店、运营、活动、知识库与团队协作的统一入口，登录后进入真实 Dify 工作台，按企业角色控制可访问能力。', '面向门店、运营、活动、知识库与团队协作的统一入口，登录后进入 MMBAI 工作台，按企业角色控制可访问能力。'],
    ['真实 Dify 工作台', 'MMBAI 工作台'],
    ['Dify 工作台', 'AI 中台'],
    ['mmb 企业身份中心', 'MMBAI 身份中心'],
    ['登录 mmb', '登录 MMBAI'],
    ['进入 Dify 工作台，管理知识库、工作流、应用与团队权限。', '进入 AI 中台，管理知识库、工作流、应用与团队权限。'],
    ['mmb. 保留所有权利。', 'MMBAI. 保留所有权利。'],
    ['mmb', 'MMBAI'],
    ['Dify', 'MMBAI'],
  ]);

  const rewriteCopy = () => {
    document.title = document.title.replaceAll('登录 mmb', '登录 MMBAI').replaceAll('Dify', 'MMBAI').replaceAll('mmb', 'MMBAI');
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        const parent = node.parentElement;
        if (!parent || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    for (const node of textNodes) {
      let value = node.nodeValue || '';
      for (const [from, to] of copyReplacements) value = value.replaceAll(from, to);
      if (value !== node.nodeValue) node.nodeValue = value;
    }
  };

  const makeLogo = (className, size) => {
    const wrap = document.createElement('div');
    wrap.className = className;
    styleLogoWrap(wrap, size);

    const img = document.createElement('img');
    styleLogoImage(img);
    wrap.appendChild(img);
    return wrap;
  };

  const ensureLogo = () => {
    rewriteCopy();
    styleLegacyEntryClasses();
    styleSecurityHighlights();

    const textBadges = Array.from(document.querySelectorAll('body div'))
      .filter((el) => el.children.length === 0 && el.textContent.trim().toLowerCase() === 'mmb');

    for (const el of textBadges) {
      if (el.querySelector('img') || el.dataset.mmbLogoPatched) continue;
      const rect = el.getBoundingClientRect();
      const large = rect.y < 100 && rect.x < window.innerWidth / 2;
      el.replaceWith(makeLogo(el.className, large ? 'large' : 'small'));
    }

    Array.from(document.images)
      .filter((img) => /logo-site(?:-dark)?\.png/.test(img.currentSrc || img.src || img.getAttribute('src') || ''))
      .forEach((img) => {
        const wrap = img.parentElement;
        if (!wrap) return;
        const rect = wrap.getBoundingClientRect();
        const large = rect.y < 100 && rect.x < window.innerWidth / 2;
        styleLogoWrap(wrap, large ? 'large' : 'small');
        styleLogoImage(img);
      });

    const entryTitle = Array.from(document.querySelectorAll('body div'))
      .find((el) => el.children.length === 0 && ['mmb 企业身份中心', 'MMBAI 身份中心'].includes(el.textContent.trim()));
    if (entryTitle) entryTitle.textContent = 'MMBAI 身份中心';
    const info = entryTitle?.parentElement;

    document.querySelectorAll('[data-mmb-entry-logo]').forEach((el) => el.remove());


    const entryCard = findEntryCard() || info;
    if (entryCard) {
      styleEntryCard(entryCard);
      const legacyIconWrap = entryCard.querySelector('img[src*="logo-embedded-chat-avatar"]')?.parentElement;
      if (legacyIconWrap && legacyIconWrap !== entryCard)
        styleEntryIconWrap(legacyIconWrap);
      entryCard.querySelectorAll('div').forEach((el) => {
        if ((el.textContent || '').trim() === 'mmb 企业身份中心') el.textContent = 'MMBAI 身份中心';
      });
    }

    if (entryTitle && info && !entryCard?.querySelector('img[src*="logo-embedded-chat-avatar"]')) {
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
      avatar.style.width = '40px';
      avatar.style.height = '40px';
      avatar.style.flex = '0 0 40px';
      avatar.style.objectFit = 'contain';
      avatar.style.borderRadius = '0';
      avatar.style.background = 'transparent';
      avatar.style.border = '0';
      avatar.style.padding = '0';
      avatar.style.boxShadow = 'none';
      avatar.style.filter = 'drop-shadow(0 5px 12px rgba(0,0,0,.18))';

      info.dataset.mmbEntryBlock = 'true';
      styleEntryCard(info);
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
